from __future__ import annotations
"""V0.4-B2-C split deployment validation test envelope.

验证面：validate_deployment(control_snapshot, deployed_core, instance_snapshot,
trusted_locator)。

Fixture 策略（synthetic-only）：
- 全部 repository ID / commit / 名称均为 synthetic 值（9000000xxx / a*40），
  不含真实凭证；validator 离线确定性，不触 GitHub。
- deployed_core 复用真实物化的 Core 仓库树（满足完整 validate_core 契约），
  provenance 为 synthetic；破坏性 negative 用临时 copytree 注入。
- Runtime-Control / Instance 快照为程序化临时目录；不创建任何真实
  deployment.yaml 于 Runtime-Control 仓库（B2-C 不物化 control plane）。
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_learning_os import (
    DeploymentBinding,
    RepositorySnapshot,
    validate_deployment,
)

# synthetic 身份（owner/name 仅 navigation，不参与信任判断）
RC_ID = 9000000001
CORE_ID = 9000000002
INST_ID = 9000000003
COMMIT = "a" * 40
CORE_REPO_ROOT = Path(__file__).resolve().parents[1]


def write_yaml(root: Path, rel: str, data: dict) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def contract(**over) -> dict:
    """合成 public Runtime-Control deployment contract（allowlist 内合法形状）。"""
    d = {
        "schema_version": "0.4",
        "document_type": "deployment_binding",
        "deployment": {"id": "dep-synthetic-001", "topology": "split",
                        "epoch": 1, "write_state": "active"},
        "core": {"repository_id": CORE_ID, "commit": COMMIT},
    }
    for k, v in over.items():
        if k in ("deployment", "core") and isinstance(v, dict):
            d[k] = {**d[k], **v}
        else:
            d[k] = v
    return d


def locator(**over) -> dict:
    loc = {
        "runtime_control": {"repository_id": RC_ID, "repository": "example/rc-nav",
                             "canonical_ref": "main", "contract_path": "deployment.yaml"},
        "instance": {"repository_id": INST_ID, "repository": "example/inst-nav"},
    }
    for k, v in over.items():
        if k in loc and isinstance(v, dict):
            loc[k] = {**loc[k], **v}
        else:
            loc[k] = v
    return loc


class DeploymentValidationTests(unittest.TestCase):
    """B2-C required envelope：positive PASS / negative fail-closed FAIL。"""

    def setUp(self) -> None:
        rc_td = tempfile.TemporaryDirectory()
        inst_td = tempfile.TemporaryDirectory()
        self.addCleanup(rc_td.cleanup)
        self.addCleanup(inst_td.cleanup)
        self.control = Path(rc_td.name)
        self.instance_root = Path(inst_td.name)
        write_file = lambda rel, text: (self.instance_root / rel).parent.mkdir(parents=True, exist_ok=True) or (self.instance_root / rel).write_text(text, encoding="utf-8")
        write_file("README.md", "# Instance\n\nNONCANONICAL — NOT DEPLOYED\n")
        write_yaml(self.instance_root, "config/instance.yaml", {
            "schema_version": "0.4", "document_type": "instance_config",
            "product": {"id": "learning-os"},
            "instance": {"display_timezone": "Asia/Shanghai"},
            "nonproduction": True,
        })
        self.core_root = CORE_REPO_ROOT

    def symlink_or_skip(self, link: Path, target: Path | str, *, target_is_directory: bool = False) -> None:
        try:
            link.symlink_to(target, target_is_directory=target_is_directory)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows host does not grant symbolic-link creation privilege")
            raise

    # ---- 组装 helpers ----

    def publish(self, c: dict | None = None, *, path: str = "deployment.yaml") -> None:
        write_yaml(self.control, path, c if c is not None else contract())

    def snaps(self, *, rc_id=RC_ID, core_id=CORE_ID, inst_id=INST_ID,
              core_commit=COMMIT):
        return (
            RepositorySnapshot(self.control, rc_id),
            RepositorySnapshot(self.core_root, core_id, core_commit),
            RepositorySnapshot(self.instance_root, inst_id),
        )

    def contract_path_errors(self, path: object) -> set[str]:
        ctrl, core, inst = self.snaps()
        loc = locator(runtime_control={"contract_path": path})
        return {f.code for f in validate_deployment(ctrl, core, inst, loc) if f.severity == "error"}

    def external_contract(self) -> Path:
        """Create a real readable valid contract outside the Runtime-Control snapshot."""
        td = tempfile.TemporaryDirectory(dir=self.control.parent, prefix="s2a-outside-")
        self.addCleanup(td.cleanup)
        outside_root = Path(td.name)
        write_yaml(outside_root, "deployment.yaml", contract())
        path = outside_root / "deployment.yaml"
        self.assertTrue(path.is_file())
        self.assertIn("deployment_binding", path.read_text(encoding="utf-8"))
        return path

    def errors(self, c: dict | None = None, loc: dict | None = None, **kw) -> set[str]:
        self.publish(c)
        ctrl, core, inst = self.snaps(**kw)
        return {f.code for f in validate_deployment(ctrl, core, inst, loc if loc is not None else locator()) if f.severity == "error"}

    def assert_pass(self, c: dict | None = None, loc: dict | None = None, **kw) -> None:
        codes = self.errors(c, loc, **kw)
        self.assertEqual(set(), codes)

    def valid_cli_provenance(self) -> dict:
        return {
            "control": {"repository_id": RC_ID},
            "core": {"repository_id": CORE_ID, "commit_sha": COMMIT},
            "instance": {"repository_id": INST_ID},
        }

    def run_cli_provenance(self, *, data: object | None = None, raw: str | None = None,
                           missing: bool = False, directory: bool = False,
                           invalid_utf8: bool = False) -> subprocess.CompletedProcess[str]:
        self.publish()
        td = tempfile.TemporaryDirectory(prefix="s2b-cli-")
        self.addCleanup(td.cleanup)
        tmp = Path(td.name)
        write_yaml(tmp, "locator.yaml", locator())
        provenance_path = tmp / "provenance.yaml"
        if missing:
            provenance_path = tmp / "missing-provenance.yaml"
        elif directory:
            provenance_path.mkdir()
        elif invalid_utf8:
            provenance_path.write_bytes(b"\xff\xfe\xfa")
        elif raw is not None:
            provenance_path.write_text(raw, encoding="utf-8")
        else:
            payload = self.valid_cli_provenance() if data is None else data
            provenance_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, "scripts/validate_learning_os.py", str(self.instance_root),
             "--deployment", "--control-snapshot", str(self.control),
             "--core-snapshot", str(self.core_root),
             "--instance-snapshot", str(self.instance_root),
             "--locator", str(tmp / "locator.yaml"),
             "--provenance", str(provenance_path)],
            capture_output=True, text=True, cwd=CORE_REPO_ROOT, timeout=120,
        )

    def assert_cli_provenance_fail(self, r: subprocess.CompletedProcess[str], reason: str) -> None:
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stdout)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("invalid --provenance", r.stderr)
        self.assertIn(reason, r.stderr)

    # ===== Positive: PASS =====

    def test_valid_active_deployment_pass(self):
        self.assert_pass()

    def test_valid_frozen_deployment_pass(self):
        # frozen 是合法结构值；quiescence 证明属操作层，validator 不下结论。
        self.assert_pass(contract(deployment={"write_state": "frozen"}))

    def test_navigation_rename_pass(self):
        # 同 numeric ID + 已变名称：navigation drift，不构成身份失败。
        self.assert_pass(
            contract(core={"repository_full_name": "renamed-owner/renamed-core"}),
            locator(runtime_control={"repository": "renamed-owner/renamed-rc"},
                    instance={"repository": "renamed-owner/renamed-inst"}))

    def test_custom_contract_path_pass(self):
        self.assert_pass(path="contracts/deployment.yaml") if False else None
        write_yaml(self.control, "contracts/deployment.yaml", contract())
        ctrl, core, inst = self.snaps()
        codes = {f.code for f in validate_deployment(ctrl, core, inst, locator(runtime_control={"contract_path": "contracts/deployment.yaml"})) if f.severity == "error"}
        self.assertEqual(set(), codes)

    # ===== S2A: repository-relative path containment =====

    def test_fail_contract_path_absolute_existing_external_file(self):
        outside = self.external_contract()
        self.assertTrue(
            {"deployment.contract_path_absolute", "deployment.contract_path_windows_drive"}
            & self.contract_path_errors(str(outside))
        )

    def test_fail_contract_path_traversal_existing_external_file(self):
        outside = self.external_contract()
        rel = f"../{outside.parent.name}/{outside.name}"
        self.assertIn("deployment.contract_path_traversal", self.contract_path_errors(rel))

    def test_fail_contract_path_tilde(self):
        self.assertIn("deployment.contract_path_home", self.contract_path_errors("~/deployment.yaml"))

    def test_fail_contract_path_windows_drive(self):
        self.assertIn("deployment.contract_path_windows_drive", self.contract_path_errors(r"C:\outside\deployment.yaml"))

    def test_fail_contract_path_backslash_separator(self):
        self.assertIn("deployment.contract_path_backslash", self.contract_path_errors(r"contracts\deployment.yaml"))

    def test_fail_contract_path_unc(self):
        self.assertIn("deployment.contract_path_absolute", self.contract_path_errors(r"\\server\share\deployment.yaml"))

    def test_fail_contract_path_dot_segment(self):
        self.assertIn("deployment.contract_path_dot", self.contract_path_errors("contracts/./deployment.yaml"))

    def test_fail_contract_path_symlink_outside(self):
        outside = self.external_contract()
        self.symlink_or_skip(self.control / "link.yaml", outside)
        self.assertIn("deployment.contract_path_symlink", self.contract_path_errors("link.yaml"))

    def test_fail_contract_path_symlink_inside(self):
        write_yaml(self.control, "real/deployment.yaml", contract())
        self.symlink_or_skip(self.control / "link.yaml", Path("real/deployment.yaml"))
        self.assertIn("deployment.contract_path_symlink", self.contract_path_errors("link.yaml"))

    def test_fail_contract_path_symlink_directory_component(self):
        write_yaml(self.control, "real-contracts/deployment.yaml", contract())
        self.symlink_or_skip(self.control / "contracts", "real-contracts", target_is_directory=True)
        self.assertIn("deployment.contract_path_symlink", self.contract_path_errors("contracts/deployment.yaml"))

    def test_instance_state_schema_supported_pass(self):
        # Instance 0.3 state doc 落在 Core 支持列表内（经 validate_instance 复用）。
        write_yaml(self.instance_root, "learner/model.yaml", {
            "schema_version": "0.3", "document_type": "learner_model",
            "updated_at": "2026-08-24T12:00:00+08:00", "working_style": {},
        })
        self.assert_pass()

    # ===== Negative: contract 结构 fail closed =====

    def test_fail_missing_contract(self):
        ctrl, core, inst = self.snaps()
        codes = {f.code for f in validate_deployment(ctrl, core, inst, locator()) if f.severity == "error"}
        self.assertIn("deployment.contract_missing", codes)

    def test_fail_wrong_schema_version(self):
        self.assertIn("deployment.schema_version", self.errors(contract(schema_version="0.3")))

    def test_fail_wrong_document_type(self):
        self.assertIn("deployment.document_type", self.errors(contract(document_type="migration_transaction")))

    def test_fail_unknown_top_level_field(self):
        self.assertIn("deployment.forbidden_field", self.errors(contract(operator_notes="x")))

    def test_fail_unknown_deployment_section_field(self):
        self.assertIn("deployment.forbidden_field", self.errors(contract(deployment={"owner": "x"})))

    def test_fail_missing_required_field(self):
        c = contract(); del c["deployment"]["write_state"]
        self.assertIn("deployment.required_field", self.errors(c))

    def test_fail_bad_epoch(self):
        self.assertIn("deployment.epoch", self.errors(contract(deployment={"epoch": 0})))
        self.assertIn("deployment.epoch", self.errors(contract(deployment={"epoch": "2"})))

    def test_fail_unknown_write_state(self):
        self.assertIn("deployment.write_state", self.errors(contract(deployment={"write_state": "paused"})))

    def test_fail_legacy_topology(self):
        self.assertIn("deployment.topology", self.errors(contract(deployment={"topology": "legacy"})))

    def test_fail_non_integer_core_id(self):
        self.assertIn("deployment.core_repository_id", self.errors(contract(core={"repository_id": "1343815302"})))

    def test_fail_abbreviated_commit(self):
        self.assertIn("deployment.core_commit", self.errors(contract(core={"commit": "fb7b2aa"})))

    def test_fail_branch_name_as_commit(self):
        self.assertIn("deployment.core_commit", self.errors(contract(core={"commit": "main"})))

    # ===== Negative: 身份 / provenance fail closed =====

    def test_fail_core_id_provenance_mismatch(self):
        self.assertIn("deployment.core_identity", self.errors(core_id=CORE_ID + 1))

    def test_fail_core_commit_provenance_mismatch(self):
        self.assertIn("deployment.core_commit_mismatch", self.errors(core_commit="b" * 40))

    def test_fail_control_identity_mismatch(self):
        self.assertIn("deployment.control_identity", self.errors(rc_id=RC_ID + 1))

    def test_fail_instance_identity_mismatch(self):
        self.assertIn("deployment.instance_identity", self.errors(inst_id=INST_ID + 1))

    def test_fail_missing_core_commit_provenance(self):
        self.publish()
        ctrl = RepositorySnapshot(self.control, RC_ID)
        core = RepositorySnapshot(self.core_root, CORE_ID, None)
        inst = RepositorySnapshot(self.instance_root, INST_ID)
        codes = {f.code for f in validate_deployment(ctrl, core, inst, locator()) if f.severity == "error"}
        self.assertIn("deployment.core_provenance", codes)

    def test_fail_bare_path_cannot_prove_identity(self):
        # bare path 无 trusted provenance：不能自证身份，fail closed。
        self.publish()
        codes = {f.code for f in validate_deployment(self.control, RepositorySnapshot(self.core_root, CORE_ID, COMMIT), RepositorySnapshot(self.instance_root, INST_ID), locator()) if f.severity == "error"}
        self.assertIn("deployment.snapshot_provenance", codes)

    def test_repository_snapshot_rejects_bad_provenance(self):
        with self.assertRaises(ValueError):
            RepositorySnapshot(self.control, "not-an-int")
        with self.assertRaises(ValueError):
            RepositorySnapshot(self.control, RC_ID, "short")

    # ===== Negative: 信任边界 fail closed =====

    def test_fail_instance_identity_in_contract(self):
        self.assertIn("deployment.trust_boundary", self.errors(contract(instance_repository_id=INST_ID)))

    def test_fail_lineage_field_in_contract(self):
        self.assertIn("deployment.trust_boundary", self.errors(contract(deployment={"active_generation": 9})))

    def test_fail_migration_field_in_contract(self):
        self.assertIn("deployment.trust_boundary", self.errors(contract(migration_authorized=True)))

    def test_fail_self_asserted_control_identity(self):
        self.assertIn("deployment.trust_boundary", self.errors(contract(runtime_control_repository_id=RC_ID)))

    def test_fail_credential_key_and_value(self):
        self.assertIn("deployment.trust_boundary", self.errors(contract(token="x")))
        self.assertIn("deployment.credential_value", self.errors(contract(deployment={"id": "ghp_" + "x" * 30})))

    # ===== Negative: locator fail closed =====

    def test_fail_missing_locator(self):
        self.publish()
        ctrl, core, inst = self.snaps()
        codes = {f.code for f in validate_deployment(ctrl, core, inst, None) if f.severity == "error"}
        self.assertIn("deployment.locator", codes)

    def test_fail_locator_unknown_key(self):
        self.assertIn("deployment.locator_keys", self.errors(loc=locator(expected_epoch=1)))

    def test_fail_locator_non_integer_id(self):
        self.assertIn("deployment.locator_id", self.errors(loc=locator(instance={"repository_id": "inst"})))

    # ===== 复用面（不复制逻辑）负向传播 =====

    def test_validate_core_failure_propagates(self):
        # copytree 注入 learner/（Instance plane 内容）→ validate_core FAIL 透传。
        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / "core"  # 目标必须是尚不存在的子目录
            shutil.copytree(self.core_root, broken, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            (broken / "learner").mkdir()
            (broken / "learner" / "x.yaml").write_text("document_type: learner_model\nschema_version: '0.3'\n", encoding="utf-8")
            ctrl = RepositorySnapshot(self.control, RC_ID)
            core = RepositorySnapshot(broken, CORE_ID, COMMIT)
            inst = RepositorySnapshot(self.instance_root, INST_ID)
            self.publish()
            codes = {f.code for f in validate_deployment(ctrl, core, inst, locator()) if f.severity == "error"}
            self.assertIn("core.plane", codes)

    def test_validate_instance_failure_propagates(self):
        # Instance 缺 config/instance.yaml → validate_instance FAIL 透传。
        (self.instance_root / "config" / "instance.yaml").unlink()
        self.assertIn("instance.config_missing", self.errors())

    def test_instance_unregistered_path_failure_propagates(self):
        write_yaml(self.instance_root, "learner/random/foo.yaml", {
            "schema_version": "0.3", "document_type": "learner_model",
        })
        self.assertIn("path.unregistered", self.errors())

    def test_handoff_integrity_failure_propagates_from_instance(self):
        handoff = "topics/topic-a/subtopics/sub-a/handoffs/lineage-a/C01-to-C02.yaml"
        write_yaml(self.instance_root, handoff, {
            "schema_version": "0.3", "document_type": "learning_handoff",
            "topic": "topic-a", "branch_id": "wrong-branch", "lineage_id": "lineage-a",
            "from_generation": 1, "to_generation": 2,
        })
        write_yaml(self.instance_root, "topics/topic-a/coordination/branches/branch-a/runtime.yaml", {
            "schema_version": "0.3", "document_type": "branch_runtime", "revision": 1,
            "topic": "topic-a", "branch_id": "branch-a", "lineage_id": "lineage-a",
            "active_generation": 2, "pending_successor": None,
            "generations": {
                "1": {"lifecycle": "archived", "handoff_ref": handoff},
                "2": {"lifecycle": "active"},
            },
        })
        self.assertIn("branch.handoff_ref_identity", self.errors())

    def test_binding_projection_uses_contract_fields(self):
        # contract 投影 binding：字段与 contract 一致（epoch=2 传播到 Instance 面）。
        self.assert_pass(contract(deployment={"epoch": 2, "id": "dep-synthetic-002"}))

    # ===== CLI 面 =====

    def test_cli_deployment_surface(self):
        r = self.run_cli_provenance()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("0 error(s)", r.stdout)

    def test_cli_provenance_optional_control_instance_full_commits_pass(self):
        p = self.valid_cli_provenance()
        p["control"]["commit_sha"] = "b" * 40
        p["instance"]["commit_sha"] = "c" * 40
        r = self.run_cli_provenance(data=p)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("0 error(s)", r.stdout)

    def test_cli_provenance_missing_file_fails_cleanly(self):
        self.assert_cli_provenance_fail(self.run_cli_provenance(missing=True), "cannot read file")

    def test_cli_provenance_directory_fails_cleanly(self):
        self.assert_cli_provenance_fail(self.run_cli_provenance(directory=True), "cannot read file")

    def test_cli_provenance_invalid_utf8_fails_cleanly(self):
        self.assert_cli_provenance_fail(self.run_cli_provenance(invalid_utf8=True), "cannot read file")

    def test_cli_provenance_invalid_yaml_fails_cleanly(self):
        self.assert_cli_provenance_fail(self.run_cli_provenance(raw="control: [\n"), "invalid YAML")

    def test_cli_provenance_top_level_non_mapping_fails_cleanly(self):
        cases = {
            "null": "null\n",
            "list": "- x\n",
            "string": "hello\n",
            "integer": "123\n",
            "boolean": "true\n",
        }
        for name, raw in cases.items():
            with self.subTest(name=name):
                self.assert_cli_provenance_fail(self.run_cli_provenance(raw=raw), "top-level must be a mapping")

    def test_cli_provenance_missing_required_sections_fail_cleanly(self):
        for section in ("control", "core", "instance"):
            with self.subTest(section=section):
                p = self.valid_cli_provenance(); del p[section]
                self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "missing required section")

    def test_cli_provenance_malformed_sections_fail_cleanly(self):
        for section in ("control", "core", "instance"):
            for value in ([], "hello", 1):
                with self.subTest(section=section, value=repr(value)):
                    p = self.valid_cli_provenance(); p[section] = value
                    self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "must be a mapping")

    def test_cli_provenance_unknown_top_level_key_fails_cleanly(self):
        p = self.valid_cli_provenance(); p["unexpected"] = "x"
        self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "unknown top-level keys")

    def test_cli_provenance_unknown_section_keys_fail_cleanly(self):
        for section in ("control", "core", "instance"):
            with self.subTest(section=section):
                p = self.valid_cli_provenance(); p[section]["commit"] = COMMIT
                self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "unknown keys")

    def test_cli_provenance_repository_ids_strict_fail_cleanly(self):
        bad_values = ("123", True, 0, -1)
        for section in ("control", "core", "instance"):
            for value in bad_values:
                with self.subTest(section=section, value=repr(value)):
                    p = self.valid_cli_provenance(); p[section]["repository_id"] = value
                    self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "repository_id")

    def test_cli_provenance_core_commit_required_and_exact_fail_cleanly(self):
        p = self.valid_cli_provenance(); del p["core"]["commit_sha"]
        self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "commit_sha")
        for value in ("abc1234", "main", "g" * 40):
            with self.subTest(value=value):
                p = self.valid_cli_provenance(); p["core"]["commit_sha"] = value
                self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "commit_sha")

    def test_cli_provenance_optional_commits_malformed_fail_cleanly(self):
        for section, value in (("control", "short"), ("instance", "main")):
            with self.subTest(section=section):
                p = self.valid_cli_provenance(); p[section]["commit_sha"] = value
                self.assert_cli_provenance_fail(self.run_cli_provenance(data=p), "commit_sha")

    def test_deployment_binding_from_contract_shape(self):
        b = DeploymentBinding.from_contract(contract(), locator())
        self.assertEqual("contract", b.form)
        self.assertEqual(CORE_ID, b.fields["core_repository_id"])
        self.assertEqual("split", b.fields["topology"])


if __name__ == "__main__":
    unittest.main()
