from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import scripts.validate_learning_os as validator_module
from scripts.validate_learning_os import (
    LEGACY_CANONICAL_DOCUMENT_TYPES,
    LEGACY_CANONICAL_PATH_RULES,
    LEGACY_SCHEMA_VERSIONS,
    ROOTS,
    Validator,
    expected_types_for_path,
)


EXPECTED_LEGACY_CANONICAL_DOCUMENT_TYPES = {
    "project_config",
    "conversation_sequence_registry",
    "lineage_control",
    "learner_background",
    "learner_model",
    "learner_calibration",
    "learner_costs",
    "learner_execution",
    "learner_knowledge",
    "curriculum",
    "topic_goal",
    "topic_plan",
    "topic_progress",
    "topic_deferred",
    "subtopic_definition",
    "subtopic_plan",
    "subtopic_progress",
    "weekly_execution",
    "daily_execution",
    "execution_session",
    "branch_registry",
    "branch_runtime",
    "branch_report",
    "coordination_event",
    "hub_runtime",
    "topic_report",
    "learning_handoff",
    "evidence",
}

EXPECTED_LEGACY_SCHEMA_VERSIONS = {
    "project_config": {"0.3"},
    "conversation_sequence_registry": {"0.3"},
    "lineage_control": {"0.3"},
    "learner_background": {"0.1"},
    "learner_model": {"0.1"},
    "learner_calibration": {"0.1"},
    "learner_costs": {"0.1"},
    "learner_execution": {"0.3"},
    "learner_knowledge": {"0.3"},
    "curriculum": {"0.1"},
    "topic_goal": {"0.3"},
    "topic_plan": {"0.3"},
    "topic_progress": {"0.3"},
    "topic_deferred": {"0.3"},
    "subtopic_definition": {"0.3"},
    "subtopic_plan": {"0.3"},
    "subtopic_progress": {"0.3"},
    "weekly_execution": {"0.3"},
    "daily_execution": {"0.3"},
    "execution_session": {"0.3"},
    "branch_registry": {"0.3"},
    "branch_runtime": {"0.3"},
    "branch_report": {"0.3"},
    "coordination_event": {"0.3"},
    "hub_runtime": {"0.3"},
    "topic_report": {"0.3"},
    "learning_handoff": {"0.3"},
    "evidence": {"0.3"},
}

CANONICAL_PATH_SAMPLES = (
    ("config/project.yaml", "project_config"),
    ("runtime/ui/conversation-sequences.yaml", "conversation_sequence_registry"),
    ("runtime/lineages/learning-os-design.yaml", "lineage_control"),
    ("learner/background.yaml", "learner_background"),
    ("learner/model.yaml", "learner_model"),
    ("learner/calibration.yaml", "learner_calibration"),
    ("learner/costs.yaml", "learner_costs"),
    ("learner/execution.yaml", "learner_execution"),
    ("learner/knowledge/foo.yaml", "learner_knowledge"),
    ("domains/foo/curriculum.yaml", "curriculum"),
    ("topics/foo/goal.yaml", "topic_goal"),
    ("topics/foo/plan.yaml", "topic_plan"),
    ("topics/foo/progress.yaml", "topic_progress"),
    ("topics/foo/deferred.yaml", "topic_deferred"),
    ("topics/foo/subtopics/bar/definition.yaml", "subtopic_definition"),
    ("topics/foo/subtopics/bar/plan.yaml", "subtopic_plan"),
    ("topics/foo/subtopics/bar/progress.yaml", "subtopic_progress"),
    ("execution/weekly/2026-W35.yaml", "weekly_execution"),
    ("topics/foo/execution/daily/2026-08-25.yaml", "daily_execution"),
    ("topics/foo/execution/sessions/s1.yaml", "execution_session"),
    ("topics/foo/coordination/branches.yaml", "branch_registry"),
    ("topics/foo/coordination/branches/main/runtime.yaml", "branch_runtime"),
    ("topics/foo/coordination/branches/main/report.yaml", "branch_report"),
    ("topics/foo/coordination/events/evt_x.yaml", "coordination_event"),
    ("coordination/hub/runtime.yaml", "hub_runtime"),
    ("topics/foo/coordination/topic-report.yaml", "topic_report"),
    ("topics/foo/handoffs/lineage-x/C01-to-C02.yaml", "learning_handoff"),
    ("topics/foo/subtopics/bar/handoffs/lineage-x/C01-to-C02.yaml", "learning_handoff"),
    ("evidence/evi_x.yaml", "evidence"),
)


def write_yaml(root: Path, rel: str, data: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def error_codes(root: Path) -> set[str]:
    return {f.code for f in Validator(root).run() if f.severity == "error"}


def valid_lineage(pending: bool = False) -> dict:
    data = {
        "schema_version": "0.3",
        "document_type": "lineage_control",
        "lineage": {"id": "learning-os-design", "kind": "project_design"},
        "active_generation": 8,
        "pending_handoff": None,
        "bootstrap": {"initial_generation": 3},
        "last_transition": {"kind": "normal_handoff", "from_generation": 7, "to_generation": 8},
    }
    if pending:
        data["active_generation"] = 7
        data["pending_handoff"] = {
            "id": "hnd_test",
            "from_generation": 7,
            "to_generation": 8,
            "anchor": {"repository": "owner/repo", "ref": "main", "canonical_head": "abc"},
            "packet": {"path": "docs/handoffs/test.md", "blob_sha": "def"},
        }
        data["last_transition"] = {"kind": "normal_handoff", "from_generation": 6, "to_generation": 7}
    return data


def valid_branch_runtime() -> dict:
    return {
        "schema_version": "0.3",
        "document_type": "branch_runtime",
        "revision": 3,
        "topic": "topic-a",
        "branch_id": "branch-main",
        "lineage_id": "branch-lineage",
        "active_generation": 2,
        "pending_successor": None,
        "generations": {
            1: {"lifecycle": "archived"},
            2: {"lifecycle": "active"},
        },
    }


def valid_sequence_registry(with_repair: bool = False) -> dict:
    data = {
        "schema_version": "0.3",
        "document_type": "conversation_sequence_registry",
        "sequence_format": {"prefix": "C", "minimum_width": 2, "allocation": "monotonic_reservation", "usage": "production_user_work_conversations"},
        "nonproduction_sequence_format": {"prefix": "T", "minimum_width": 2, "allocation": "monotonic_reservation", "usage": "acceptance_test_migration_simulation"},
        "scopes": {
            "learning_os": {"last_allocated": 5},
            "acceptance:learning_os": {"last_allocated": 1},
        },
    }
    if with_repair:
        data["repair_history"] = [{
            "scope": "learning_os",
            "previous_last_allocated": 7,
            "repaired_last_allocated": 5,
            "orphaned_suffix": ["C06", "C07"],
            "reason": "proven synthetic/orphan suffix",
            "repaired_at": "2026-08-22T08:22:51+08:00",
            "authority": "learning-os-design generation 8",
        }]
    return data


def valid_evidence() -> dict:
    return {
        "schema_version": "0.3",
        "document_type": "evidence",
        "id": "evi_1",
        "observed_at": "2026-08-22T08:00:00+08:00",
        "observation": {"kind": "learner_explanation", "summary": "example"},
        "interpretation": {"direction": "support", "diagnosticity": "medium", "novelty": "high", "confidence": "high"},
        "targets": [{"type": "capability", "domain": "domain-a", "concept": "node.a", "capability": "explanation"}],
    }


def valid_coordination_event(event_id: str = "evt_1") -> dict:
    return {
        "schema_version": "0.3",
        "document_type": "coordination_event",
        "id": event_id,
        "observed_at": "2026-08-25T08:00:00+08:00",
        "producer": {"type": "branch", "id": "main"},
        "target_scope": "topic",
        "type": "progress_transition",
        "subtype": "test",
        "hub_attention": {"level": "review"},
        "payload": {},
        "refs": {},
    }


def valid_knowledge(evidence_id: str = "evi_1") -> dict:
    return {
        "schema_version": "0.3",
        "document_type": "learner_knowledge",
        "revision": 1,
        "domain": "domain-a",
        "concepts": {
            "node.a": {
                "capabilities": {
                    "explanation": {
                        "state": "provisional",
                        "confidence": "medium",
                        "evidence_refs": {"support": [evidence_id], "challenge": []},
                    }
                }
            }
        },
    }


def valid_curriculum() -> dict:
    return {
        "schema_version": "0.1",
        "document_type": "curriculum",
        "domain": {"id": "domain-a", "title": "Domain A"},
        "curriculum_version": "1",
        "nodes": {"node.a": {"title": "Node A", "kind": "concept"}},
        "edges": [],
        "aliases": {"node.old": "node.a"},
    }


def valid_project_config() -> dict:
    return {
        "schema_version": "0.3",
        "document_type": "project_config",
        "project": {"id": "learning-os"},
        "repository": {"full_name": "owner/repo"},
        "time": {"display_timezone": "Asia/Shanghai"},
        "runtime": {},
        "protocol": {},
    }


def valid_topic_bundle(root: Path) -> None:
    write_yaml(root, "topics/topic-a/goal.yaml", {
        "schema_version": "0.3", "document_type": "topic_goal", "revision": 2,
        "topic": {"id": "topic-a", "title": "Topic A"}, "goal": {"purpose": {"value": "learn"}},
    })
    write_yaml(root, "topics/topic-a/plan.yaml", {
        "schema_version": "0.3", "document_type": "topic_plan", "revision": 3, "topic": "topic-a",
        "plan": {"status": "active", "based_on": {"goal_revision": 2}, "milestones": []},
    })
    write_yaml(root, "topics/topic-a/progress.yaml", {
        "schema_version": "0.3", "document_type": "topic_progress", "revision": 4, "topic": "topic-a",
        "plan_revision": 3, "lifecycle": "active", "milestones": {},
    })
    write_yaml(root, "topics/topic-a/subtopics/sub-a/definition.yaml", {
        "schema_version": "0.3", "document_type": "subtopic_definition",
        "subtopic": {"id": "sub-a", "topic": "topic-a", "title": "Sub A", "kind": "standard", "lifecycle": "active"},
    })
    write_yaml(root, "topics/topic-a/subtopics/sub-a/plan.yaml", {
        "schema_version": "0.3", "document_type": "subtopic_plan", "revision": 5, "topic": "topic-a", "subtopic": "sub-a",
        "plan": {"status": "active", "based_on": {"topic_plan_revision": 3}, "milestones": [{
            "id": "m1", "title": "M1", "exit_criteria": [],
            "curriculum_refs": [{"type": "curriculum_node", "domain": "domain-a", "id": "node.a"}],
        }]},
    })
    write_yaml(root, "topics/topic-a/subtopics/sub-a/progress.yaml", {
        "schema_version": "0.3", "document_type": "subtopic_progress", "revision": 6, "topic": "topic-a", "subtopic": "sub-a",
        "plan_revision": 5, "milestones": {"m1": {"status": "in_progress"}},
    })


class ValidatorTests(unittest.TestCase):
    def make_repo(self):
        td = tempfile.TemporaryDirectory()
        return td, Path(td.name)

    def assert_valid(self, root: Path) -> None:
        findings = Validator(root).run()
        errors = [f.render() for f in findings if f.severity == "error"]
        self.assertEqual([], errors)

    # PASS fixtures
    def test_current_canonical_document_type_allowlist_matches_schema(self):
        self.assertEqual(EXPECTED_LEGACY_CANONICAL_DOCUMENT_TYPES, LEGACY_CANONICAL_DOCUMENT_TYPES)
        self.assertEqual(28, len(LEGACY_CANONICAL_DOCUMENT_TYPES))

    def test_legacy_schema_version_matrix_matches_canonical_contract(self):
        self.assertEqual(EXPECTED_LEGACY_SCHEMA_VERSIONS, LEGACY_SCHEMA_VERSIONS)
        self.assertEqual(LEGACY_CANONICAL_DOCUMENT_TYPES, set(LEGACY_SCHEMA_VERSIONS))
        for versions in LEGACY_SCHEMA_VERSIONS.values():
            self.assertIsInstance(versions, (set, frozenset))
            self.assertTrue(versions)
            self.assertTrue(all(isinstance(v, str) and v.strip() for v in versions))
        for t in ("topic_deferred", "daily_execution", "branch_report", "hub_runtime", "topic_report"):
            self.assertEqual({"0.3"}, LEGACY_SCHEMA_VERSIONS[t])

    def test_legacy_path_registry_matches_complete_canonical_contract(self):
        self.assertEqual(29, len(LEGACY_CANONICAL_PATH_RULES))
        self.assertEqual(LEGACY_CANONICAL_DOCUMENT_TYPES, {t for _, t in LEGACY_CANONICAL_PATH_RULES})
        self.assertEqual(2, sum(1 for _, t in LEGACY_CANONICAL_PATH_RULES if t == "learning_handoff"))
        for path, expected_type in CANONICAL_PATH_SAMPLES:
            with self.subTest(path=path):
                self.assertEqual((expected_type,), expected_types_for_path(path))
                self.assertIn(path.split("/", 1)[0], ROOTS)

    def test_valid_curriculum_schema_01_boundary(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "domains/domain-a/curriculum.yaml", valid_curriculum())
        self.assertNotIn("yaml.schema_version_unsupported", error_codes(root))

    def test_valid_project_config_schema_03_boundary(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "config/project.yaml", valid_project_config())
        self.assert_valid(root)

    def test_valid_active_project_lineage(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "runtime/lineages/learning-os-design.yaml", valid_lineage())
        self.assert_valid(root)

    def test_valid_pending_handoff(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "runtime/lineages/learning-os-design.yaml", valid_lineage(pending=True))
        self.assert_valid(root)

    def test_valid_learning_branch_runtime(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "topics/topic-a/coordination/branches/branch-main/runtime.yaml", valid_branch_runtime())
        self.assert_valid(root)

    def test_valid_production_sequence_registry(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "runtime/ui/conversation-sequences.yaml", valid_sequence_registry())
        self.assert_valid(root)

    def test_valid_orphan_repair_history(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "runtime/ui/conversation-sequences.yaml", valid_sequence_registry(with_repair=True))
        self.assert_valid(root)

    def test_valid_evidence_to_knowledge_ref(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "evidence/evi_1.yaml", valid_evidence())
        write_yaml(root, "learner/knowledge/domain-a.yaml", valid_knowledge())
        self.assert_valid(root)

    def test_valid_coordination_event_identity(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "topics/foo/coordination/events/evt_1.yaml", valid_coordination_event())
        self.assertNotIn("path.identity", error_codes(root))

    def test_valid_lazy_and_previously_underregistered_paths(self):
        cases = (
            ("topics/foo/deferred.yaml", {"schema_version": "0.3", "document_type": "topic_deferred"}),
            ("topics/foo/execution/daily/2026-08-25.yaml", {"schema_version": "0.3", "document_type": "daily_execution"}),
            ("topics/foo/coordination/branches/main/report.yaml", {"schema_version": "0.3", "document_type": "branch_report"}),
            ("coordination/hub/runtime.yaml", {"schema_version": "0.3", "document_type": "hub_runtime"}),
            ("topics/foo/coordination/topic-report.yaml", {"schema_version": "0.3", "document_type": "topic_report"}),
        )
        for rel, data in cases:
            with self.subTest(rel=rel):
                td, root = self.make_repo(); self.addCleanup(td.cleanup)
                write_yaml(root, rel, data)
                codes = error_codes(root)
                self.assertNotIn("path.unregistered", codes)
                self.assertNotIn("path.ambiguous", codes)
                self.assertNotIn("path.document_type", codes)

    def test_valid_topic_subtopic_plan_progress_refs(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "domains/domain-a/curriculum.yaml", valid_curriculum())
        valid_topic_bundle(root)
        self.assert_valid(root)

    def test_sparse_repository_is_valid(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "config/project.yaml", valid_project_config())
        self.assert_valid(root)

    # FAIL fixtures
    def test_fail_missing_schema_version_preserves_existing_code(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_project_config(); del data["schema_version"]
        write_yaml(root, "config/project.yaml", data)
        self.assertIn("yaml.schema_version", error_codes(root))

    def test_fail_malformed_schema_versions_do_not_crash(self):
        cases = (
            ("null", None), ("integer", 123), ("bool_true", True), ("bool_false", False),
            ("list", []), ("dict", {}), ("empty", ""), ("whitespace", "   "), ("float", 0.3),
        )
        for name, value in cases:
            with self.subTest(name=name):
                td, root = self.make_repo(); self.addCleanup(td.cleanup)
                data = valid_project_config(); data["schema_version"] = value
                write_yaml(root, "config/project.yaml", data)
                findings = Validator(root).run()
                codes = {f.code for f in findings if f.severity == "error"}
                self.assertIn("yaml.schema_version_invalid", codes)
                self.assertNotIn("document.required", codes)

    def test_fail_unsupported_schema_versions_stop_structural_dispatch(self):
        for value in ("999", "future", "0.4", " 0.3 ", "0.30"):
            with self.subTest(schema_version=value):
                td, root = self.make_repo(); self.addCleanup(td.cleanup)
                write_yaml(root, "config/project.yaml", {"schema_version": value, "document_type": "project_config"})
                codes = error_codes(root)
                self.assertIn("yaml.schema_version_unsupported", codes)
                self.assertNotIn("document.required", codes)
                self.assertNotIn("path.unregistered", codes)

    def test_fail_curriculum_schema_03_boundary(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_curriculum(); data["schema_version"] = "0.3"
        write_yaml(root, "domains/domain-a/curriculum.yaml", data)
        codes = error_codes(root)
        self.assertIn("yaml.schema_version_unsupported", codes)
        self.assertNotIn("document.required", codes)

    def test_fail_project_config_schema_01_boundary(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_project_config(); data["schema_version"] = "0.1"
        write_yaml(root, "config/project.yaml", data)
        self.assertIn("yaml.schema_version_unsupported", error_codes(root))

    def test_fail_missing_document_type_on_unregistered_path(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        self.assertIsNone(Validator.expected("topics/custom.yaml"))
        write_yaml(root, "topics/custom.yaml", {"schema_version": "0.3"})
        codes = error_codes(root)
        self.assertIn("yaml.document_type", codes)
        self.assertNotIn("path.unregistered", codes)

    def test_fail_malformed_document_types_do_not_crash(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        self.assertIsNone(Validator.expected("topics/custom.yaml"))
        cases = (
            ("null", None),
            ("integer", 123),
            ("bool_true", True),
            ("bool_false", False),
            ("list", []),
            ("dict", {}),
            ("empty", ""),
            ("whitespace", "   "),
        )
        for name, value in cases:
            with self.subTest(name=name):
                write_yaml(root, "topics/custom.yaml", {"schema_version": "0.3", "document_type": value})
                findings = Validator(root).run()
                codes = {f.code for f in findings if f.severity == "error"}
                self.assertIn("yaml.document_type_invalid", codes)
                self.assertNotIn("yaml.schema_version_invalid", codes)
                self.assertNotIn("yaml.schema_version_unsupported", codes)
                self.assertNotIn("path.unregistered", codes)

    def test_fail_unknown_document_types_on_unregistered_path(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        self.assertIsNone(Validator.expected("topics/custom.yaml"))
        for value in ("definitely_not_canonical", "core_config", "instance_config", "deployment_binding"):
            with self.subTest(document_type=value):
                write_yaml(root, "topics/custom.yaml", {"schema_version": "0.3", "document_type": value})
                codes = error_codes(root)
                self.assertIn("yaml.document_type_unknown", codes)
                self.assertNotIn("yaml.schema_version_invalid", codes)
                self.assertNotIn("yaml.schema_version_unsupported", codes)
                self.assertNotIn("path.unregistered", codes)

    def test_fail_historical_v02_document_types_on_unregistered_path(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        self.assertIsNone(Validator.expected("topics/custom.yaml"))
        for value in ("domain_goal", "domain_plan", "domain_state", "domain_deferred"):
            with self.subTest(document_type=value):
                write_yaml(root, "topics/custom.yaml", {"schema_version": "0.3", "document_type": value})
                codes = error_codes(root)
                self.assertIn("yaml.document_type_unknown", codes)
                self.assertNotIn("path.unregistered", codes)

    def test_fail_unregistered_known_current_paths(self):
        cases = (
            ("topics/foo/custom.yaml", {"schema_version": "0.3", "document_type": "topic_goal"}),
            ("topics/foo/evidence.yaml", {**valid_evidence(), "id": "evidence"}),
            ("domains/foo/custom.yaml", valid_curriculum()),
            ("evidence/nested/evi_1.yaml", valid_evidence()),
            ("topics/foo/coordination/random.yaml", valid_coordination_event("random")),
        )
        for rel, data in cases:
            with self.subTest(rel=rel):
                td, root = self.make_repo(); self.addCleanup(td.cleanup)
                write_yaml(root, rel, data)
                codes = error_codes(root)
                self.assertIn("path.unregistered", codes)
                self.assertNotIn("document.required", codes)

    def test_fail_path_registry_ambiguity_does_not_first_match(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "config/project.yaml", valid_project_config())
        duplicate_rules = LEGACY_CANONICAL_PATH_RULES + (LEGACY_CANONICAL_PATH_RULES[0],)
        with patch.object(validator_module, "LEGACY_CANONICAL_PATH_RULES", duplicate_rules):
            codes = error_codes(root)
        self.assertIn("path.ambiguous", codes)
        self.assertNotIn("path.document_type", codes)
        self.assertNotIn("document.required", codes)

    def test_fail_path_placeholder_dot_segments_are_unregistered(self):
        cases = (
            "topics/./goal.yaml",
            "topics/../goal.yaml",
            "domains/./curriculum.yaml",
            "evidence/...yaml",
        )
        for path in cases:
            with self.subTest(path=path):
                self.assertEqual((), expected_types_for_path(path))

    def test_fail_invalid_handoff_filename_is_unregistered(self):
        self.assertEqual((), expected_types_for_path("topics/foo/handoffs/lineage-x/handoff.yaml"))
        self.assertEqual((), expected_types_for_path("topics/foo/handoffs/lineage-x/C00-to-C01.yaml"))

    def test_fail_evidence_identity_mismatch(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_evidence(); data["id"] = "evi_2"
        write_yaml(root, "evidence/evi_1.yaml", data)
        codes = error_codes(root)
        self.assertIn("path.identity", codes)
        self.assertNotIn("document.required", codes)

    def test_fail_coordination_event_identity_mismatch(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "topics/foo/coordination/events/evt_1.yaml", valid_coordination_event("evt_2"))
        codes = error_codes(root)
        self.assertIn("path.identity", codes)
        self.assertNotIn("document.required", codes)

    def test_fail_two_active_branch_generations(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_branch_runtime(); data["generations"][1]["lifecycle"] = "active"
        write_yaml(root, "topics/topic-a/coordination/branches/branch-main/runtime.yaml", data)
        self.assertIn("branch.active_count", error_codes(root))

    def test_fail_missing_active_generation_record(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_branch_runtime(); data["active_generation"] = 3
        write_yaml(root, "topics/topic-a/coordination/branches/branch-main/runtime.yaml", data)
        self.assertIn("branch.active_record", error_codes(root))

    def test_fail_pending_handoff_wrong_from_generation(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_lineage(pending=True); data["pending_handoff"]["from_generation"] = 6
        write_yaml(root, "runtime/lineages/learning-os-design.yaml", data)
        self.assertIn("lineage.pending_from", error_codes(root))

    def test_fail_invalid_evidence_ref(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "learner/knowledge/domain-a.yaml", valid_knowledge("evi_missing"))
        self.assertIn("reference.evidence_missing", error_codes(root))

    def test_fail_invalid_curriculum_ref(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "domains/domain-a/curriculum.yaml", valid_curriculum())
        valid_topic_bundle(root)
        plan_path = root / "topics/topic-a/subtopics/sub-a/plan.yaml"
        data = yaml.safe_load(plan_path.read_text()); data["plan"]["milestones"][0]["curriculum_refs"][0]["id"] = "missing.node"
        write_yaml(root, "topics/topic-a/subtopics/sub-a/plan.yaml", data)
        self.assertIn("reference.curriculum_node", error_codes(root))

    def test_fail_plan_revision_mismatch(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "domains/domain-a/curriculum.yaml", valid_curriculum()); valid_topic_bundle(root)
        path = root / "topics/topic-a/subtopics/sub-a/progress.yaml"; data = yaml.safe_load(path.read_text()); data["plan_revision"] = 4
        write_yaml(root, "topics/topic-a/subtopics/sub-a/progress.yaml", data)
        self.assertIn("revision.subtopic_progress_plan", error_codes(root))

    def test_fail_illegal_enum(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "evidence/evi_1.yaml", valid_evidence())
        data = yaml.safe_load((root / "evidence/evi_1.yaml").read_text()); data["interpretation"]["confidence"] = "certain"
        write_yaml(root, "evidence/evi_1.yaml", data)
        self.assertIn("enum.invalid", error_codes(root))

    def test_fail_malformed_sequence_repair(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_sequence_registry(with_repair=True); data["repair_history"][0]["orphaned_suffix"] = ["C07"]
        write_yaml(root, "runtime/ui/conversation-sequences.yaml", data)
        self.assertIn("sequence.repair_suffix", error_codes(root))

    def test_fail_production_nonproduction_scope_confusion(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        data = valid_sequence_registry(); data["scopes"]["acceptance:bogus:scope"] = {"last_allocated": 1}
        write_yaml(root, "runtime/ui/conversation-sequences.yaml", data)
        self.assertIn("sequence.nonproduction_scope", error_codes(root))

    def test_fail_invalid_document_type_for_path(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "topics/topic-a/goal.yaml", {"schema_version": "0.3", "document_type": "topic_plan"})
        codes = error_codes(root)
        self.assertIn("path.document_type", codes)
        self.assertNotIn("yaml.schema_version_unsupported", codes)
        self.assertNotIn("document.required", codes)

    def test_valid_open_weekly_projection_may_be_stale(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "topics/topic-a/subtopics/sub-a/progress.yaml", {
            "schema_version": "0.3", "document_type": "subtopic_progress", "revision": 3,
            "topic": "topic-a", "subtopic": "sub-a", "plan_revision": 1, "milestones": {},
        })
        write_yaml(root, "execution/weekly/2026-W34.yaml", {
            "schema_version": "0.3", "document_type": "weekly_execution", "revision": 1,
            "window": {"id": "2026-W34"}, "current_outcomes": [], "closing": None,
            "projection": {"observed_at": "2026-08-21T08:22:48+08:00", "source_revisions": [
                {"ref": "topics/topic-a/subtopics/sub-a/progress.yaml", "revision": 2}
            ], "reconciliation": "read_time"},
        })
        self.assert_valid(root)

    def test_fail_open_weekly_missing_projection(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "execution/weekly/2026-W34.yaml", {
            "schema_version": "0.3", "document_type": "weekly_execution", "revision": 1,
            "window": {"id": "2026-W34"}, "current_outcomes": [], "closing": None,
        })
        self.assertIn("weekly.projection", error_codes(root))


if __name__ == "__main__":
    unittest.main()
