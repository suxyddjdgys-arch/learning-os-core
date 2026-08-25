from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_learning_os import LEGACY_CANONICAL_DOCUMENT_TYPES, Validator


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

    def test_valid_topic_subtopic_plan_progress_refs(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "domains/domain-a/curriculum.yaml", valid_curriculum())
        valid_topic_bundle(root)
        self.assert_valid(root)

    def test_sparse_repository_is_valid(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        write_yaml(root, "config/project.yaml", {
            "schema_version": "0.3", "document_type": "project_config",
            "project": {"id": "learning-os"}, "repository": {"full_name": "owner/repo"},
            "time": {"display_timezone": "Asia/Shanghai"}, "runtime": {}, "protocol": {},
        })
        self.assert_valid(root)

    # FAIL fixtures
    def test_fail_missing_document_type_on_unregistered_path(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        self.assertIsNone(Validator.expected("topics/custom.yaml"))
        write_yaml(root, "topics/custom.yaml", {"schema_version": "0.3"})
        self.assertIn("yaml.document_type", error_codes(root))

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

    def test_fail_unknown_document_types_on_unregistered_path(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        self.assertIsNone(Validator.expected("topics/custom.yaml"))
        for value in ("definitely_not_canonical", "core_config", "instance_config", "deployment_binding"):
            with self.subTest(document_type=value):
                write_yaml(root, "topics/custom.yaml", {"schema_version": "0.3", "document_type": value})
                self.assertIn("yaml.document_type_unknown", error_codes(root))

    def test_fail_historical_v02_document_types_on_unregistered_path(self):
        td, root = self.make_repo(); self.addCleanup(td.cleanup)
        self.assertIsNone(Validator.expected("topics/custom.yaml"))
        for value in ("domain_goal", "domain_plan", "domain_state", "domain_deferred"):
            with self.subTest(document_type=value):
                write_yaml(root, "topics/custom.yaml", {"schema_version": "0.3", "document_type": value})
                self.assertIn("yaml.document_type_unknown", error_codes(root))

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
        write_yaml(root, "topics/topic-a/progress.yaml", {"schema_version": "0.3", "document_type": "topic_plan"})
        self.assertIn("path.document_type", error_codes(root))

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
