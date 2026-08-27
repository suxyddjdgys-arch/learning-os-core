from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.runtime_adapter import (
    CasConflict,
    DeploymentGuard,
    DeploymentResolver,
    GuardRejected,
    MaterializedRepository,
    ResolutionError,
    TransitionRejected,
    pointer_rollback_allowed,
    validate_deployment_transition,
    validate_initial_cutover,
)

ROOT = Path(__file__).resolve().parents[1]
RC_ID, CORE_ID, INSTANCE_ID = 9000000101, 9000000102, 9000000103
CORE_COMMIT = "a" * 40
RC_COMMIT = "b" * 40
INSTANCE_COMMIT = "c" * 40


def locator(**runtime_control):
    return {
        "runtime_control": {
            "repository_id": RC_ID,
            "canonical_ref": "main",
            "contract_path": "deployment.yaml",
            **runtime_control,
        },
        "instance": {"repository_id": INSTANCE_ID, "canonical_ref": "main"},
    }


def contract(*, epoch=1, write_state="active", core_commit=CORE_COMMIT):
    return {
        "schema_version": "0.4",
        "document_type": "deployment_binding",
        "deployment": {
            "id": "dep-runtime-test",
            "topology": "split",
            "epoch": epoch,
            "write_state": write_state,
        },
        "core": {"repository_id": CORE_ID, "commit": core_commit},
    }


class FakeProvider:
    def __init__(self, control: Path, instance: Path):
        self.control = control
        self.instance = instance
        self.contract = contract()
        self.unavailable = False
        self.cas_sha = "d" * 40
        self.calls = []

    def materialize(self, repository_id, ref):
        self.calls.append(("materialize", repository_id, ref))
        if repository_id == RC_ID:
            self._write_contract()
            return MaterializedRepository(self.control, RC_ID, RC_COMMIT, "renamed/rc")
        if repository_id == CORE_ID:
            if ref != CORE_COMMIT:
                raise ResolutionError("exact Core unavailable")
            return MaterializedRepository(ROOT, CORE_ID, CORE_COMMIT, "renamed/core")
        if repository_id == INSTANCE_ID:
            return MaterializedRepository(self.instance, INSTANCE_ID, INSTANCE_COMMIT, "renamed/instance")
        raise ResolutionError("unknown numeric repository identity")

    def _write_contract(self):
        (self.control / "deployment.yaml").write_text(
            yaml.safe_dump(self.contract, sort_keys=False), encoding="utf-8"
        )

    def read_text(self, repository_id, ref, path):
        self.calls.append(("read", repository_id, ref, path))
        if self.unavailable:
            raise ResolutionError("outage")
        if repository_id != RC_ID or ref != "main" or path != "deployment.yaml":
            raise ResolutionError("wrong read")
        return yaml.safe_dump(self.contract, sort_keys=False), "e" * 40, RC_COMMIT

    def update_text(self, repository_id, branch, path, content, expected_blob_sha, message):
        self.calls.append(("update", repository_id, branch, path, expected_blob_sha))
        if expected_blob_sha != self.cas_sha:
            raise CasConflict("stale blob")
        return "f" * 40


class RuntimeAdapterTests(unittest.TestCase):
    def setUp(self):
        rc_td = tempfile.TemporaryDirectory()
        inst_td = tempfile.TemporaryDirectory()
        self.addCleanup(rc_td.cleanup)
        self.addCleanup(inst_td.cleanup)
        self.control = Path(rc_td.name)
        self.instance = Path(inst_td.name)
        shutil.copytree(
            ROOT.parent / "learning-os-instance",
            self.instance,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        self.provider = FakeProvider(self.control, self.instance)

    def session(self):
        return DeploymentResolver(self.provider).resolve(locator()).context

    def test_zero_history_bootstrap_resolves_exact_planes(self):
        resolved = DeploymentResolver(self.provider).resolve(locator())
        self.assertEqual(CORE_COMMIT, resolved.context.core_commit)
        self.assertEqual(INSTANCE_ID, resolved.context.instance_repository_id)

    def test_navigation_rename_does_not_change_identity(self):
        resolved = DeploymentResolver(self.provider).resolve(locator(repository="old/name"))
        self.assertEqual(RC_ID, resolved.context.runtime_control_repository_id)

    def test_core_main_advance_is_not_used(self):
        resolved = DeploymentResolver(self.provider).resolve(locator())
        self.assertIn(("materialize", CORE_ID, CORE_COMMIT), self.provider.calls)
        self.assertEqual(CORE_COMMIT, resolved.context.core_commit)

    def test_exact_core_unavailable_fails_closed(self):
        self.provider.contract = contract(core_commit="9" * 40)
        with self.assertRaises(ResolutionError):
            DeploymentResolver(self.provider).resolve(locator())

    def test_wrong_instance_identity_fails_closed(self):
        bad = locator()
        bad["instance"]["repository_id"] = INSTANCE_ID + 10
        with self.assertRaises(ResolutionError):
            DeploymentResolver(self.provider).resolve(bad)

    def test_malformed_control_fails_closed(self):
        self.provider.read_text = lambda *args: ("[]", "e" * 40, RC_COMMIT)
        with self.assertRaises(ResolutionError):
            DeploymentResolver(self.provider).resolve(locator())

    def test_active_fresh_session_guard_passes(self):
        DeploymentGuard(self.provider).check(self.session())

    def test_frozen_guard_blocks_before_mutation(self):
        session = self.session()
        self.provider.contract = contract(write_state="frozen")
        with self.assertRaises(GuardRejected):
            DeploymentGuard(self.provider).guarded_update(
                session,
                branch="main",
                path="learner/model.yaml",
                content="x",
                expected_blob_sha=self.provider.cas_sha,
                message="test",
            )
        self.assertFalse(any(call[0] == "update" for call in self.provider.calls))

    def test_stale_epoch_blocks_before_mutation(self):
        session = self.session()
        self.provider.contract = contract(epoch=2)
        with self.assertRaises(GuardRejected):
            DeploymentGuard(self.provider).check(session)

    def test_core_promotion_blocks_stale_session(self):
        session = self.session()
        self.provider.contract = contract(epoch=2, core_commit="9" * 40)
        with self.assertRaises(GuardRejected):
            DeploymentGuard(self.provider).check(session)

    def test_control_outage_blocks_write(self):
        session = self.session()
        self.provider.unavailable = True
        with self.assertRaises(GuardRejected):
            DeploymentGuard(self.provider).check(session)

    def test_generation_guard_is_independent(self):
        session = self.session()
        with self.assertRaisesRegex(GuardRejected, "generation"):
            DeploymentGuard(self.provider).guarded_update(
                session,
                branch="main",
                path="learner/model.yaml",
                content="x",
                expected_blob_sha=self.provider.cas_sha,
                message="test",
                expected_generation=9,
                generation_reader=lambda: 10,
            )
        self.assertFalse(any(call[0] == "update" for call in self.provider.calls))

    def test_target_cas_is_independent(self):
        session = self.session()
        with self.assertRaises(CasConflict):
            DeploymentGuard(self.provider).guarded_update(
                session,
                branch="main",
                path="learner/model.yaml",
                content="x",
                expected_blob_sha="0" * 40,
                message="test",
            )

    def test_successful_guarded_update_orders_guard_before_cas(self):
        session = self.session()
        result = DeploymentGuard(self.provider).guarded_update(
            session,
            branch="main",
            path="learner/model.yaml",
            content="x",
            expected_blob_sha=self.provider.cas_sha,
            message="test",
            expected_generation=9,
            generation_reader=lambda: 9,
        )
        self.assertEqual("f" * 40, result)
        names = [call[0] for call in self.provider.calls]
        self.assertLess(names.index("read"), names.index("update"))


class DeploymentTransitionTests(unittest.TestCase):
    def test_initial_cutover_is_split_frozen_epoch_one(self):
        validate_initial_cutover(contract(write_state="frozen"))

    def test_initial_cutover_active_is_rejected(self):
        with self.assertRaises(TransitionRejected):
            validate_initial_cutover(contract(write_state="active"))

    def test_normal_freeze_and_activate(self):
        active = contract(write_state="active")
        frozen = contract(write_state="frozen")
        validate_deployment_transition(active, frozen)
        validate_deployment_transition(frozen, active)

    def test_core_promotion_is_frozen_exact_epoch_increment(self):
        old = contract(epoch=4, write_state="frozen", core_commit="8" * 40)
        new = contract(epoch=5, write_state="frozen", core_commit="9" * 40)
        validate_deployment_transition(old, new)

    def test_active_core_pin_change_is_rejected(self):
        old = contract(epoch=4, core_commit="8" * 40)
        new = contract(epoch=5, core_commit="9" * 40)
        with self.assertRaises(TransitionRejected):
            validate_deployment_transition(old, new)

    def test_epoch_decrease_is_rejected(self):
        with self.assertRaises(TransitionRejected):
            validate_deployment_transition(contract(epoch=4), contract(epoch=3))

    def test_epoch_skip_is_rejected(self):
        old = contract(epoch=4, write_state="frozen", core_commit="8" * 40)
        new = contract(epoch=6, write_state="frozen", core_commit="9" * 40)
        with self.assertRaises(TransitionRejected):
            validate_deployment_transition(old, new)

    def test_epoch_change_without_promotion_is_rejected(self):
        with self.assertRaises(TransitionRejected):
            validate_deployment_transition(contract(epoch=4), contract(epoch=5))

    def test_core_repository_identity_change_is_rejected(self):
        old, new = contract(), contract()
        new["core"]["repository_id"] += 1
        with self.assertRaises(TransitionRejected):
            validate_deployment_transition(old, new)

    def test_deployment_id_change_is_rejected(self):
        old, new = contract(), contract()
        new["deployment"]["id"] = "other"
        with self.assertRaises(TransitionRejected):
            validate_deployment_transition(old, new)

    def test_interrupted_frozen_transaction_can_resume_forward(self):
        frozen = contract(epoch=2, write_state="frozen", core_commit="9" * 40)
        active = contract(epoch=2, write_state="active", core_commit="9" * 40)
        validate_deployment_transition(frozen, frozen)
        validate_deployment_transition(frozen, active)

    def test_prewrite_pointer_rollback_is_allowed(self):
        self.assertTrue(pointer_rollback_allowed(post_cutover_instance_mutated=False))

    def test_postwrite_pointer_rollback_is_rejected(self):
        self.assertFalse(pointer_rollback_allowed(post_cutover_instance_mutated=True))


if __name__ == "__main__":
    unittest.main()
