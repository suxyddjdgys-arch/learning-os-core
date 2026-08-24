from __future__ import annotations
"""V0.4-B2-B split-aware Instance validation test envelope.

验证面：validate_instance(instance_snapshot, deployed_core, trusted_context)。

Fixture 策略（synthetic-only）：
- 全部 fixture 为程序化临时目录（tempfile），不落盘 tests/fixtures/**，
  不含任何真实 learner 状态、真实 Evidence 或真实凭证。
- deployed_core 是合成物化的 Core 快照（仅 load_core 所需的最小面：
  config/core.yaml + domains/<base>/curriculum.yaml）。
- trusted_context 是合成 trusted deployment context；live binding
  （epoch enforcement / write_state routing / ID 解析）属 B2-C，不在本面实现。

另含一条集成测试：用真实物化 Core 仓库树作为 deployed_core（证明 exact
Core snapshot 满足 load_core 契约）。真实 Instance 快照的 exact 验证在
saga Step 10/14 以显式记录完成，不在 CI 单测中依赖 sibling checkout。
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_learning_os import validate_instance

# 与授权记录一致的真实 repository ID（仅作为 synthetic context 的取值）
CORE_REPO_ID = 1343815302
INSTANCE_REPO_ID = 1343815864
CORE_REPO_ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "base-domain"
BASE_VERSION = "0.2"
EVI_ID = "evi-synthetic-001"


def write_file(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_yaml(root: Path, rel: str, data: dict) -> None:
    write_file(root, rel, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def trusted_context(core_commit: str | None = None) -> dict:
    """合成 trusted deployment context（B2-B 唯一定义的 synthetic 形态）。"""
    return {
        "context_type": "synthetic",
        "core_repository_id": CORE_REPO_ID,
        "core_commit": core_commit or "a" * 40,
        "instance_repository_id": INSTANCE_REPO_ID,
        "topology": "noncanonical-split",
        "epoch": 1,
        "write_state": "not_deployed",
    }


# ---- 合成 Core 快照（deployed_core 最小面）----

def core_curriculum(domain: str = DOMAIN, version: str = BASE_VERSION) -> dict:
    return {
        "schema_version": "0.1",
        "document_type": "curriculum",
        "domain": {"id": domain, "title": domain},
        "curriculum_version": version,
        "nodes": {
            f"{domain}.foundation": {"title": "Foundation", "kind": "concept"},
            f"{domain}.application": {"title": "Application", "kind": "application"},
        },
        "edges": [{"id": f"{domain}.edge-1", "relation": "supports", "strength": "medium"}],
        "aliases": {f"{domain}.alias": f"{domain}.foundation"},
        "capability_profiles": {"conceptual_core": {"conceptual_structure": "expected"}},
    }


def make_core(root: Path, domain: str = DOMAIN, version: str = BASE_VERSION,
              state_schemas: list | None = None) -> Path:
    write_yaml(root, "config/core.yaml", {
        "schema_version": "0.4",
        "document_type": "core_config",
        "product": {"id": "learning-os", "name": "Learning OS"},
        "manifest": {
            "release": "0.4.0-candidate",
            "supported_instance_state_schema_versions": state_schemas if state_schemas is not None else ["0.3"],
            "canonical_status": "noncanonical",
            "deployment_status": "not_deployed",
        },
    })
    write_yaml(root, f"domains/{domain}/curriculum.yaml", core_curriculum(domain, version))
    return root


# ---- Instance 文档构造器（全部 synthetic state schema 0.3）----

def instance_config_doc() -> dict:
    return {
        "schema_version": "0.4",
        "document_type": "instance_config",
        "updated_at": "2026-08-24T12:00:00+08:00",
        "product": {"id": "learning-os", "name": "Learning OS"},
        "instance": {"display_timezone": "Asia/Shanghai"},
        "nonproduction": True,
    }


def make_instance(root: Path) -> Path:
    write_file(root, "README.md", "# Learning OS — Instance\n\nStatus: NONCANONICAL V0.4 TARGET — NOT DEPLOYED\n")
    write_yaml(root, "config/instance.yaml", instance_config_doc())
    return root


def extension_doc(domain: str = DOMAIN, version: str = BASE_VERSION, revision: int = 1,
                  nodes: dict | None = None, edges: list | None = None,
                  aliases: dict | None = None, capability_profiles: dict | None = None,
                  probes: list | None = None) -> dict:
    doc: dict = {
        "schema_version": "0.4",
        "document_type": "curriculum_extension",
        "domain": domain,
        "base_version": version,
        "extension_revision": revision,
    }
    if nodes is not None:
        doc["nodes"] = nodes
    if edges is not None:
        doc["edges"] = edges
    if aliases is not None:
        doc["aliases"] = aliases
    if capability_profiles is not None:
        doc["capability_profiles"] = capability_profiles
    if probes is not None:
        doc["probes"] = probes
    return doc


def write_full_state(root: Path, *, curriculum_refs: list, provenance: list,
                     handoff_ref: str, topic: str = "modern-language-models",
                     subtopic: str = "language-modeling", knowledge_schema: str = "0.3",
                     evidence_extra: dict | None = None, plan_provenance_extra: dict | None = None) -> None:
    """写一套完整合法的 Instance 0.3 状态文档；关键参数由各测试注入。"""
    t, s = topic, subtopic
    write_yaml(root, f"learner/knowledge/{t}.yaml", {
        "schema_version": knowledge_schema, "document_type": "learner_knowledge",
        "revision": 1, "domain": DOMAIN,
        "concepts": {f"{DOMAIN}.foundation": {"capabilities": {"explanation": {
            "state": "provisional", "confidence": "low",
            "evidence_refs": {"support": [EVI_ID]},
        }}}},
    })
    evi = {
        "schema_version": "0.3", "document_type": "evidence", "id": EVI_ID,
        "observed_at": "2026-08-24T10:00:00+08:00",
        "observation": "synthetic observation",
        "interpretation": {"direction": "support", "diagnosticity": "low",
                           "novelty": "low", "confidence": "low"},
        "targets": [f"{DOMAIN}.foundation"],
    }
    if evidence_extra:
        evi.update(evidence_extra)
    write_yaml(root, f"evidence/{EVI_ID}.yaml", evi)
    write_yaml(root, f"topics/{t}/goal.yaml", {
        "schema_version": "0.3", "document_type": "topic_goal",
        "revision": 1, "topic": t, "goal": {"statement": "synthetic goal"},
    })
    write_yaml(root, f"topics/{t}/plan.yaml", {
        "schema_version": "0.3", "document_type": "topic_plan",
        "revision": 1, "topic": t,
        "plan": {"status": "active", "based_on": {"goal_revision": 1, "curricula": provenance}},
    })
    write_yaml(root, f"topics/{t}/progress.yaml", {
        "schema_version": "0.3", "document_type": "topic_progress",
        "revision": 1, "topic": t, "plan_revision": 1, "lifecycle": "active", "milestones": {},
    })
    write_yaml(root, f"topics/{t}/subtopics/{s}/definition.yaml", {
        "schema_version": "0.3", "document_type": "subtopic_definition",
        "subtopic": {"id": s, "kind": "standard", "lifecycle": "active"},
    })
    write_yaml(root, f"topics/{t}/subtopics/{s}/plan.yaml", {
        "schema_version": "0.3", "document_type": "subtopic_plan",
        "revision": 1, "topic": t, "subtopic": s,
        "plan": {"status": "active", "based_on": {"topic_plan_revision": 1},
                 "milestones": [{"id": "m1", "curriculum_refs": curriculum_refs}]},
    })
    write_yaml(root, f"topics/{t}/subtopics/{s}/progress.yaml", {
        "schema_version": "0.3", "document_type": "subtopic_progress",
        "revision": 1, "topic": t, "subtopic": s, "plan_revision": 1, "milestones": {},
    })
    handoff_rel = f"topics/{t}/subtopics/{s}/handoffs/{t}-main-lineage/C01-to-C02.yaml"
    write_yaml(root, handoff_rel, {
        "schema_version": "0.3", "document_type": "learning_handoff",
        "topic": t, "branch_id": f"{s}-main", "lineage_id": f"{t}-main-lineage",
        "from_generation": 1, "to_generation": 2,
    })
    write_yaml(root, f"topics/{t}/coordination/branches.yaml", {
        "schema_version": "0.3", "document_type": "branch_registry",
        "revision": 1, "topic": t, "branches": {f"{s}-main": {"role": "main", "lifecycle": "active"}},
    })
    write_yaml(root, f"topics/{t}/coordination/branches/{s}-main/runtime.yaml", {
        "schema_version": "0.3", "document_type": "branch_runtime",
        "revision": 1, "topic": t, "branch_id": f"{s}-main", "lineage_id": f"{t}-main-lineage",
        "active_generation": 2, "pending_successor": None,
        "generations": {"1": {"lifecycle": "archived", "handoff_ref": handoff_ref},
                        "2": {"lifecycle": "active"}},
    })
    write_yaml(root, "execution/weekly/2026-w34.yaml", {
        "schema_version": "0.3", "document_type": "weekly_execution",
        "revision": 1, "window": {"start": "2026-08-24", "end": "2026-08-30"},
    })
    write_yaml(root, "runtime/ui/conversation-sequences.yaml", {
        "schema_version": "0.3", "document_type": "conversation_sequence_registry",
        "sequence_format": {"prefix": "C", "minimum_width": 2,
                            "allocation": "monotonic_reservation", "usage": "synthetic_test"},
        "scopes": {"learning_os": {"last_allocated": 1, "bootstrap_basis": "synthetic"}},
    })


class _Unset:
    """哨兵类：区分“未提供 ctx（用合成默认）”与“显式传入 None（缺失 context）”。"""


_UNSET = _Unset()


class InstanceValidationTests(unittest.TestCase):
    """B2-B required test envelope：positive PASS / negative FAIL。"""

    def setUp(self) -> None:
        core_td = tempfile.TemporaryDirectory()
        inst_td = tempfile.TemporaryDirectory()
        self.addCleanup(core_td.cleanup)
        self.addCleanup(inst_td.cleanup)
        self.core = make_core(Path(core_td.name))
        self.instance = make_instance(Path(inst_td.name))

    def errors(self, instance: Path | None = None, core: Path | None = None,
               ctx: object = _UNSET) -> set[str]:
        findings = validate_instance(
            instance if instance is not None else self.instance,
            core if core is not None else self.core,
            trusted_context() if ctx is _UNSET else ctx,
        )
        return {f.code for f in findings if f.severity == "error"}

    def assert_pass(self, instance: Path | None = None, core: Path | None = None,
                    ctx: object = _UNSET) -> None:
        errors = [f.render() for f in validate_instance(
            instance if instance is not None else self.instance,
            core if core is not None else self.core,
            trusted_context() if ctx is _UNSET else ctx,
        ) if f.severity == "error"]
        self.assertEqual([], errors)

    def valid_refs(self, node: str, domain: str = DOMAIN) -> list:
        return [{"type": "curriculum_node", "domain": domain, "id": node}]

    def valid_legacy_provenance(self, version: str = BASE_VERSION) -> list:
        return [{"domain": DOMAIN, "curriculum_version": version}]

    def valid_new_provenance(self, version: str = BASE_VERSION, revision: int = 1) -> list:
        return [{"domain": DOMAIN, "base_version": version, "extension_revision": revision}]

    def handoff_ref_ok(self) -> str:
        return "topics/modern-language-models/subtopics/language-modeling/handoffs/modern-language-models-main-lineage/C01-to-C02.yaml"

    # ===== Positive: PASS =====

    def test_minimal_instance_config_pass(self):
        # minimal instance_config：仅 README + config/instance.yaml 即合法。
        self.assert_pass()

    def test_valid_state_documents_schema_03_pass(self):
        # 全套 0.3 状态文档（learner/Evidence/Topic/Subtopic/branch/weekly/sequence）。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_valid_core_base_reference_pass(self):
        # subtopic_plan 的 curriculum_refs 解析到 Core base 节点。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_additive_extension_pass(self):
        # additive extension：新增节点/边，不触碰 Core base；引用经合并视图解析。
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(nodes={f"{DOMAIN}.local-extension": {"title": "Local", "kind": "application"}}))
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.local-extension"),
                         provenance=self.valid_new_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_new_local_domain_pass(self):
        # 新本地 Domain（curriculum/local/**）不与 Core base 冲突即合法。
        write_yaml(self.instance, "curriculum/local/new-domain/curriculum.yaml", {
            "schema_version": "0.3", "document_type": "curriculum",
            "domain": {"id": "new-domain", "title": "New Domain"},
            "curriculum_version": "1.0",
            "nodes": {"new-domain.root": {"title": "Root", "kind": "concept"}},
            "edges": [], "aliases": {},
        })
        write_full_state(self.instance, curriculum_refs=self.valid_refs("new-domain.root", "new-domain"),
                         provenance=[{"domain": "new-domain", "curriculum_version": "1.0"}],
                         handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_new_local_probe_pass(self):
        # extension 新增 local probe（additive probes 列表）。
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(nodes={f"{DOMAIN}.probe-node": {"title": "Probe Node", "kind": "skill"}},
                                 probes=[{"id": f"{DOMAIN}.probe-1", "prompt": "synthetic probe"}]))
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.probe-node"),
                         provenance=self.valid_new_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_legacy_provenance_pass(self):
        # legacy form（curriculum_version）对 Core base 仍可解析。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_new_provenance_pass(self):
        # new form（base_version + extension_revision）在存在 extension 时可解析。
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(nodes={f"{DOMAIN}.local-extension": {"title": "Local", "kind": "application"}}))
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_new_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_branch_runtime_pass(self):
        # branch_runtime（学习 lineage，Instance 拥有）结构合法。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_safe_in_root_handoff_ref_pass(self):
        # handoff_ref 指向 Instance root 内既有 learning_handoff 文档。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assert_pass()

    def test_real_core_snapshot_as_deployed_core_pass(self):
        # 集成：真实物化 Core 仓库树作为 deployed_core（minimal instance）。
        self.assert_pass(core=CORE_REPO_ROOT)

    def test_cli_instance_surface_pass(self):
        # CLI 面：--instance + --core-snapshot + --trusted-context（file 形态）。
        ctx_file = self.instance.parent / "trusted-context.yaml"
        write_file(self.instance.parent, "trusted-context.yaml", yaml.safe_dump(trusted_context(), sort_keys=False))
        result = subprocess.run(
            [sys.executable, str(CORE_REPO_ROOT / "scripts/validate_learning_os.py"),
             str(self.instance), "--instance", "--core-snapshot", str(self.core),
             "--trusted-context", str(ctx_file)],
            capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    # ===== Negative: FAIL =====

    def test_fail_state_schema_04(self):
        # 状态文档 schema_version 0.4：Core 仅支持 0.3（D2），fail closed。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok(),
                         knowledge_schema="0.4")
        self.assertIn("instance.state_schema_unsupported", self.errors())

    def test_fail_unsupported_state_schema(self):
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok(),
                         knowledge_schema="0.5")
        self.assertIn("instance.state_schema_unsupported", self.errors())

    def test_fail_missing_core(self):
        # deployed_core 缺失：fail closed。
        self.assertIn("instance.core_snapshot", self.errors(core=self.instance / "no-such-core"))

    def test_fail_missing_trusted_context(self):
        # trusted context 缺失：fail closed。
        self.assertIn("instance.trusted_context", self.errors(ctx=None))

    def test_fail_core_owned_top_level_directory(self):
        # Core 拥有的顶层目录（domains/）出现在 Instance 快照。
        write_yaml(self.instance, "domains/base-domain/curriculum.yaml", core_curriculum())
        self.assertIn("instance.core_owned_top", self.errors())

    def test_fail_core_owned_config_file(self):
        # config/core.yaml 属 Core plane，禁止出现在 Instance config/。
        write_file(self.instance, "config/core.yaml", "# core contract\n")
        self.assertIn("instance.config_forbidden", self.errors())

    def test_fail_lineage_control_in_instance(self):
        # project-design lineage_control 属 Control plane：目录与文档双拒绝。
        write_yaml(self.instance, "runtime/lineages/learning-os-design.yaml", {
            "schema_version": "0.3", "document_type": "lineage_control",
            "lineage": {"id": "learning-os-design"}, "active_generation": 8, "pending_handoff": None,
        })
        errors = self.errors()
        self.assertIn("instance.private_lineage", errors)
        self.assertIn("instance.forbidden_document", errors)

    def test_fail_deployment_authority_fields(self):
        # deployment/control authority 字段（deployment_epoch 等）禁止出现在 Instance。
        config = instance_config_doc()
        config["deployment_epoch"] = 2
        write_yaml(self.instance, "config/instance.yaml", config)
        self.assertIn("instance.authority_key", self.errors())

    def test_fail_core_node_collision(self):
        # extension 节点与 Core base 节点同 ID = shadow，fail closed。
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(nodes={f"{DOMAIN}.foundation": {"title": "Shadow", "kind": "concept"}}))
        self.assertIn("instance.node_collision", self.errors())

    def test_fail_core_edge_collision(self):
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(edges=[{"id": f"{DOMAIN}.edge-1", "relation": "extends", "strength": "weak"}]))
        self.assertIn("instance.edge_collision", self.errors())

    def test_fail_capability_override(self):
        # extension capability_profiles 覆盖 Core base profile = fail closed。
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(capability_profiles={"conceptual_core": {"transfer": "not_expected"}}))
        self.assertIn("instance.capability_override", self.errors())

    def test_fail_delete_tombstone_core(self):
        # extension 节点携带 tombstone = 删除语义，additive-only 拒绝。
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(nodes={f"{DOMAIN}.foundation": {"tombstone": True}}))
        self.assertIn("instance.core_delete", self.errors())

    def test_fail_core_alias_redirect(self):
        # extension 重定义 Core base alias = redirect，fail closed。
        write_yaml(self.instance, "curriculum/extensions/base-extension.yaml",
                   extension_doc(aliases={f"{DOMAIN}.alias": f"{DOMAIN}.application"}))
        self.assertIn("instance.alias_redirect", self.errors())

    def test_fail_same_id_different_content(self):
        # 本地 Domain 与 Core base 同 ID 不同内容 = shadow，fail closed。
        write_yaml(self.instance, "curriculum/local/base-domain/curriculum.yaml", {
            "schema_version": "0.3", "document_type": "curriculum",
            "domain": {"id": DOMAIN, "title": "Shadow Domain"},
            "curriculum_version": "9.9",
            "nodes": {f"{DOMAIN}.other": {"title": "Other", "kind": "concept"}},
            "edges": [], "aliases": {},
        })
        self.assertIn("instance.domain_shadow", self.errors())

    def test_fail_unresolved_semantic_reference(self):
        # curriculum_refs 指向有效 domain 中不存在的节点。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.nonexistent"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok())
        self.assertIn("reference.curriculum_node", self.errors())

    def test_fail_traversal_handoff_ref(self):
        # handoff_ref 携带 ../ 穿越：fail closed。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(),
                         handoff_ref="../../outside/secret.yaml")
        self.assertIn("instance.ref_traversal", self.errors())

    def test_fail_absolute_handoff_ref(self):
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(),
                         handoff_ref="/etc/passwd")
        self.assertIn("instance.ref_absolute", self.errors())

    def test_fail_cross_plane_reference(self):
        # 引用落在 Instance 自有 plane 之外（protocol/ 属 Core plane）。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(),
                         handoff_ref="protocol/runtime-core.md")
        self.assertIn("instance.ref_cross_plane", self.errors())

    def test_fail_unknown_document_type(self):
        write_yaml(self.instance, "learner/notes.yaml", {
            "schema_version": "0.3", "document_type": "mystery_document",
        })
        self.assertIn("instance.unknown_document_type", self.errors())

    def test_fail_malformed_evidence(self):
        # Evidence 使用 legacy classification_confidence = malformed。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=self.valid_legacy_provenance(), handoff_ref=self.handoff_ref_ok(),
                         evidence_extra={"classification_confidence": "high"})
        self.assertIn("evidence.legacy_confidence", self.errors())

    def test_fail_ambiguous_provenance_form(self):
        # 同一条目同时携带 legacy 与 new form 字段 = ambiguous。
        write_full_state(self.instance, curriculum_refs=self.valid_refs(f"{DOMAIN}.foundation"),
                         provenance=[{"domain": DOMAIN, "curriculum_version": BASE_VERSION,
                                      "base_version": BASE_VERSION, "extension_revision": 1}],
                         handoff_ref=self.handoff_ref_ok())
        self.assertIn("instance.provenance_ambiguous", self.errors())

    # ===== Negative: trusted context fail-closed 形态 =====

    def test_fail_trusted_context_unknown_key(self):
        ctx = trusted_context()
        ctx["live_endpoint"] = "https://github.example"
        self.assertIn("instance.trusted_context_keys", self.errors(ctx=ctx))

    def test_fail_trusted_context_live_type(self):
        # live binding 形态未在 B2-B 定义：拒绝。
        ctx = trusted_context()
        ctx["context_type"] = "live"
        self.assertIn("instance.trusted_context_type", self.errors(ctx=ctx))

    def test_fail_trusted_context_bad_commit(self):
        ctx = trusted_context()
        ctx["core_commit"] = "not-a-commit"
        self.assertIn("instance.trusted_context_commit", self.errors(ctx=ctx))

    def test_fail_trusted_context_missing_key(self):
        ctx = trusted_context()
        del ctx["epoch"]
        self.assertIn("instance.trusted_context_missing", self.errors(ctx=ctx))

    # ===== Negative: Instance config 边界 =====

    def test_fail_instance_config_missing(self):
        (self.instance / "config/instance.yaml").unlink()
        self.assertIn("instance.config_missing", self.errors())

    def test_fail_instance_config_core_override(self):
        # instance.yaml 重定义 Core 拥有区块（chat_routing 等）= fail closed。
        config = instance_config_doc()
        config["chat_routing"] = {"modes": ["learning"]}
        write_yaml(self.instance, "config/instance.yaml", config)
        self.assertIn("instance.core_override", self.errors())

    def test_fail_instance_product_mismatch(self):
        # product.id 与 deployed Core 不一致。
        config = instance_config_doc()
        config["product"]["id"] = "other-os"
        write_yaml(self.instance, "config/instance.yaml", config)
        self.assertIn("instance.product_mismatch", self.errors())


if __name__ == "__main__":
    unittest.main()
