#!/usr/bin/env python3
"""Deterministic mechanical validator for Learning OS canonical YAML."""
from __future__ import annotations
import argparse, re
from dataclasses import dataclass
from pathlib import Path
import yaml

ROOTS={"config","runtime","learner","domains","topics","execution","coordination","evidence"}
PLANNED={"planned","in_progress","completed","blocked","deferred","dropped"}; CONF={"low","medium","high"}
CAP={"provisional","supported","conflicted","unsupported"}; EDIR={"support","challenge","neutral","deferred"}
GEN={"active","idle","handoff_pending","archived","deprecated"}; BROLE={"hub","main","practice","deep_dive"}; BLIFE={"active","idle","retired"}
TLIFE={"active","paused","completed","cancelled"}; SLIFE={"active","paused","completed","merged","split","discarded"}; SKIND={"standard","prerequisite_support","integration"}
NKIND={"concept","procedure","theorem","skill","representation","application","integration"}; EREL={"requires","supports","extends","contrasts_with","applies_to","integrates_with","generalizes","motivates","reinforces"}; ESTR={"weak","medium","strong"}

@dataclass(frozen=True)
class Finding:
    severity:str; code:str; path:str; message:str
    def render(self): return f"{self.severity.upper():7} {self.code:28} {self.path}: {self.message}"

class Validator:
    def __init__(self,root:Path): self.root=root.resolve(); self.docs={}; self.findings=[]; self.evidence=set(); self.curricula={}
    def error(self,c,p,m): self.findings.append(Finding("error",c,p,m))
    def enum(self,p,f,v,a):
        if v not in a: self.error("enum.invalid",p,f"{f}={v!r} not in {sorted(a)}")
    @staticmethod
    def expected(p):
        exact={"config/project.yaml":"project_config","runtime/ui/conversation-sequences.yaml":"conversation_sequence_registry","learner/background.yaml":"learner_background","learner/model.yaml":"learner_model","learner/calibration.yaml":"learner_calibration","learner/costs.yaml":"learner_costs","learner/execution.yaml":"learner_execution"}
        if p in exact:return exact[p]
        pats=[(r"runtime/lineages/[^/]+\.yaml","lineage_control"),(r"learner/knowledge/[^/]+\.yaml","learner_knowledge"),(r"domains/[^/]+/curriculum\.yaml","curriculum"),(r"evidence/[^/]+\.yaml","evidence"),(r"execution/weekly/[^/]+\.yaml","weekly_execution"),(r"topics/[^/]+/goal\.yaml","topic_goal"),(r"topics/[^/]+/plan\.yaml","topic_plan"),(r"topics/[^/]+/progress\.yaml","topic_progress"),(r"topics/[^/]+/deferred\.yaml","topic_deferred"),(r"topics/[^/]+/subtopics/[^/]+/definition\.yaml","subtopic_definition"),(r"topics/[^/]+/subtopics/[^/]+/plan\.yaml","subtopic_plan"),(r"topics/[^/]+/subtopics/[^/]+/progress\.yaml","subtopic_progress"),(r"topics/[^/]+/coordination/branches\.yaml","branch_registry"),(r"topics/[^/]+/coordination/branches/[^/]+/runtime\.yaml","branch_runtime"),(r"topics/[^/]+/execution/sessions/[^/]+\.yaml","execution_session"),(r"topics/[^/]+/subtopics/[^/]+/handoffs/[^/]+/[^/]+\.yaml","learning_handoff")]
        return next((t for r,t in pats if re.fullmatch(r,p)),None)
    def load(self):
        for f in sorted(self.root.rglob("*.yaml")):
            rp=f.relative_to(self.root)
            if not rp.parts or rp.parts[0] not in ROOTS: continue
            p=rp.as_posix()
            try:d=yaml.safe_load(f.read_text(encoding="utf-8"))
            except Exception as e:self.error("yaml.parse",p,str(e));continue
            if not isinstance(d,dict):self.error("yaml.mapping",p,"canonical YAML must be mapping");continue
            self.docs[p]=d
        for p,d in self.docs.items():
            if d.get("document_type")=="evidence" and isinstance(d.get("id"),str):
                if d["id"] in self.evidence:self.error("evidence.duplicate_id",p,d["id"])
                self.evidence.add(d["id"])
            if d.get("document_type")=="curriculum" and isinstance(d.get("domain"),dict) and isinstance(d["domain"].get("id"),str):self.curricula[d["domain"]["id"]]=d
    def structural(self):
        req={"project_config":("project","repository","time","runtime","protocol"),"conversation_sequence_registry":("sequence_format","scopes"),"lineage_control":("lineage","active_generation","pending_handoff"),"learner_knowledge":("revision","domain","concepts"),"curriculum":("domain","curriculum_version","nodes"),"topic_goal":("revision","topic","goal"),"topic_plan":("revision","topic","plan"),"topic_progress":("revision","topic","plan_revision","lifecycle","milestones"),"subtopic_definition":("subtopic",),"subtopic_plan":("revision","topic","subtopic","plan"),"subtopic_progress":("revision","topic","subtopic","plan_revision","milestones"),"weekly_execution":("revision","window"),"branch_registry":("revision","topic","branches"),"branch_runtime":("revision","topic","branch_id","lineage_id","active_generation","pending_successor","generations"),"execution_session":("id","topic","branch","meaningful_learning"),"learning_handoff":("topic","branch_id","lineage_id","from_generation","to_generation"),"evidence":("id","observed_at","observation","interpretation","targets")}
        for p,d in self.docs.items():
            if "schema_version" not in d:self.error("yaml.schema_version",p,"missing schema_version")
            if "document_type" not in d:self.error("yaml.document_type",p,"missing document_type");continue
            e=self.expected(p)
            if e and d["document_type"]!=e:self.error("path.document_type",p,f"expected {e}, found {d['document_type']}")
            for k in req.get(d["document_type"],()):
                if k not in d:self.error("document.required",p,f"missing {k}")
            t=d["document_type"]
            if t=="topic_plan":self.enum(p,"plan.status",(d.get("plan")or{}).get("status"),{"awaiting_intake","provisional","active","paused"})
            elif t=="topic_progress":
                self.enum(p,"lifecycle",d.get("lifecycle"),TLIFE)
                for k,x in (d.get("milestones")or{}).items():
                    if isinstance(x,dict):self.enum(p,f"milestones.{k}.status",x.get("status"),PLANNED)
            elif t=="subtopic_definition":s=d.get("subtopic")or{};self.enum(p,"subtopic.kind",s.get("kind"),SKIND);self.enum(p,"subtopic.lifecycle",s.get("lifecycle"),SLIFE)
            elif t=="subtopic_plan":self.enum(p,"plan.status",(d.get("plan")or{}).get("status"),{"provisional","active","paused"})
            elif t=="subtopic_progress":
                for k,x in (d.get("milestones")or{}).items():
                    if isinstance(x,dict):self.enum(p,f"milestones.{k}.status",x.get("status"),PLANNED)
            elif t=="learner_knowledge":
                for c,x in (d.get("concepts")or{}).items():
                    for a,y in ((x or{}).get("capabilities")or{}).items():self.enum(p,f"{c}.{a}.state",y.get("state"),CAP);self.enum(p,f"{c}.{a}.confidence",y.get("confidence"),CONF)
            elif t=="evidence":
                x=d.get("interpretation")or{};self.enum(p,"interpretation.direction",x.get("direction"),EDIR)
                for k in ("diagnosticity","novelty","confidence"):self.enum(p,f"interpretation.{k}",x.get(k),CONF)
                if "classification_confidence" in x or "classification_confidence" in d:self.error("evidence.legacy_confidence",p,"use interpretation.confidence")
            elif t=="curriculum":
                for k,x in (d.get("nodes")or{}).items():
                    if isinstance(x,dict):self.enum(p,f"nodes.{k}.kind",x.get("kind"),NKIND)
                for x in d.get("edges")or[]:
                    if isinstance(x,dict):self.enum(p,"edge.relation",x.get("relation"),EREL);self.enum(p,"edge.strength",x.get("strength"),ESTR)
            elif t=="branch_registry":
                for k,x in (d.get("branches")or{}).items():self.enum(p,f"branches.{k}.role",x.get("role"),BROLE);self.enum(p,f"branches.{k}.lifecycle",x.get("lifecycle"),BLIFE)
            elif t=="branch_runtime":
                for k,x in (d.get("generations")or{}).items():
                    if isinstance(x,dict):self.enum(p,f"generations.{k}.lifecycle",x.get("lifecycle"),GEN)
            elif t=="weekly_execution":
                for s in ("baseline_outcomes","current_outcomes"):
                    for x in d.get(s)or[]:
                        if isinstance(x,dict) and "status" in x:self.enum(p,f"{s}.{x.get('id')}.status",x.get("status"),PLANNED)
    def refs(self):
        for p,d in self.docs.items():
            t=d.get("document_type")
            if t=="topic_progress":
                q=self.docs.get(f"topics/{d.get('topic')}/plan.yaml")
                if q and d.get("plan_revision")!=q.get("revision"):self.error("revision.topic_progress_plan",p,"plan_revision != current topic plan revision")
            elif t=="subtopic_progress":
                q=self.docs.get(f"topics/{d.get('topic')}/subtopics/{d.get('subtopic')}/plan.yaml")
                if q and d.get("plan_revision")!=q.get("revision"):self.error("revision.subtopic_progress_plan",p,"plan_revision != current subtopic plan revision")
            elif t=="topic_plan":
                q=self.docs.get(f"topics/{d.get('topic')}/goal.yaml");r=((d.get("plan")or{}).get("based_on")or{}).get("goal_revision")
                if q and isinstance(r,int) and r>q.get("revision",r):self.error("revision.topic_plan_goal_future",p,"goal_revision points to future revision")
            elif t=="subtopic_plan":
                q=self.docs.get(f"topics/{d.get('topic')}/plan.yaml");r=((d.get("plan")or{}).get("based_on")or{}).get("topic_plan_revision")
                if q and isinstance(r,int) and r>q.get("revision",r):self.error("revision.subtopic_plan_topic_future",p,"topic_plan_revision points to future revision")
                for m in (d.get("plan")or{}).get("milestones")or[]:
                    for r in (m or{}).get("curriculum_refs")or[]:
                        if not isinstance(r,dict) or r.get("type")!="curriculum_node":continue
                        c=self.curricula.get(r.get("domain"));n=r.get("id")
                        if not c:self.error("reference.curriculum_domain",p,f"missing curriculum {r.get('domain')}");continue
                        nodes,aliases=c.get("nodes")or{},c.get("aliases")or{};a=aliases.get(n)
                        if isinstance(a,dict):a=a.get("to")or a.get("target")or a.get("id")
                        if n not in nodes and (not isinstance(a,str) or a not in nodes):self.error("reference.curriculum_node",p,f"unresolved curriculum node {r.get('domain')}:{n}")
            elif t=="learner_knowledge":
                for c,x in (d.get("concepts")or{}).items():
                    for a,y in ((x or{}).get("capabilities")or{}).items():
                        for side in ("support","challenge"):
                            for r in ((y or{}).get("evidence_refs")or{}).get(side)or[]:
                                if r not in self.evidence:self.error("reference.evidence_missing",p,f"{c}.{a} -> {r}")
    @staticmethod
    def prod(s):return s in {"learning_os","learning_hub","model_review"} or bool(re.fullmatch(r"(?:topic_hub:[^:]+|learning_(?:main|practice|deep_dive):[^:]+:[^:]+)",s))
    def sequence(self):
        p="runtime/ui/conversation-sequences.yaml";d=self.docs.get(p)
        if not d:return
        scopes=d.get("scopes")or{};np=False
        for s,x in scopes.items():
            if not isinstance(x,dict):self.error("sequence.scope_record",p,s);continue
            n=x.get("last_allocated")
            if not isinstance(n,int) or isinstance(n,bool) or n<0:self.error("sequence.last_allocated",p,s)
            if s.startswith(("acceptance:","test:")):np=True;self.prod(s.split(":",1)[1]) or self.error("sequence.nonproduction_scope",p,s)
            elif not self.prod(s):self.error("sequence.production_scope",p,s)
        if np and (d.get("nonproduction_sequence_format")or{}).get("prefix")!="T":self.error("sequence.nonproduction_prefix",p,"non-production prefix must be T")
        w=(d.get("sequence_format")or{}).get("minimum_width",2)
        for i,r in enumerate(d.get("repair_history")or[]):
            if not isinstance(r,dict):self.error("sequence.repair_record",p,str(i));continue
            a,b=r.get("previous_last_allocated"),r.get("repaired_last_allocated")
            if not self.prod(str(r.get("scope"))):self.error("sequence.repair_scope",p,str(i))
            if not all(isinstance(x,int) and not isinstance(x,bool) for x in (a,b)) or not 0<=b<a:self.error("sequence.repair_range",p,str(i));continue
            if r.get("orphaned_suffix")!=[f"C{n:0{w}d}" for n in range(b+1,a+1)]:self.error("sequence.repair_suffix",p,str(i))
            if any(not r.get(k) for k in ("reason","repaired_at","authority")):self.error("sequence.repair_provenance",p,str(i))
            cur=(scopes.get(r.get("scope"))or{}).get("last_allocated")
            if isinstance(cur,int) and cur<b:self.error("sequence.repair_current",p,str(i))
    def authority(self):
        for p,d in self.docs.items():
            t=d.get("document_type")
            if t=="lineage_control":
                a=d.get("active_generation");i=(d.get("bootstrap")or{}).get("initial_generation")
                if not isinstance(a,int) or isinstance(a,bool):self.error("lineage.active_generation",p,"must be integer");continue
                if isinstance(i,int) and a<i:self.error("lineage.initial_generation",p,"active < initial")
                h=d.get("pending_handoff")
                if h is not None:
                    if not isinstance(h,dict):self.error("lineage.pending_shape",p,"must be null or mapping");continue
                    if h.get("from_generation")!=a:self.error("lineage.pending_from",p,"from_generation != active_generation")
                    if not isinstance(h.get("to_generation"),int) or h["to_generation"]<=a:self.error("lineage.pending_to",p,"to_generation must advance")
                    if not (h.get("packet")or{}).get("path") or not (h.get("packet")or{}).get("blob_sha"):self.error("lineage.pending_packet",p,"missing packet identity")
                    z=h.get("anchor")or{}
                    if not z.get("repository") or not z.get("ref") or not z.get("canonical_head"):self.error("lineage.pending_anchor",p,"incomplete anchor")
                z=(d.get("last_transition")or{}).get("to_generation")
                if isinstance(z,int) and z>a:self.error("lineage.last_transition",p,"transition exceeds active generation")
            elif t=="branch_runtime":
                a=d.get("active_generation");g=d.get("generations")or{};r=g.get(a,g.get(str(a))) if isinstance(a,int) else None
                if r is None:self.error("branch.active_record",p,f"missing generation {a}");continue
                act=[k for k,x in g.items() if isinstance(x,dict) and x.get("lifecycle")=="active"];h=d.get("pending_successor")
                if h is None:
                    if len(act)!=1:self.error("branch.active_count",p,f"active={act}")
                    if r.get("lifecycle")!="active":self.error("branch.active_lifecycle",p,"active record not active")
                else:
                    n=h.get("generation") if isinstance(h,dict) else h
                    if r.get("lifecycle")!="handoff_pending":self.error("branch.pending_lifecycle",p,"source not handoff_pending")
                    if not isinstance(n,int) or n<=a:self.error("branch.pending_generation",p,"pending successor must advance")
                for x in g.values():
                    ref=x.get("handoff_ref") if isinstance(x,dict) else None
                    if ref and not (self.root/ref).exists():self.error("branch.handoff_ref",p,ref)
    def weekly(self):
        for p,d in self.docs.items():
            if d.get("document_type")!="weekly_execution" or d.get("current_outcomes") is None or d.get("closing") is not None:continue
            x=d.get("projection")
            if not isinstance(x,dict):self.error("weekly.projection",p,"open current_outcomes require provenance");continue
            if not x.get("observed_at"):self.error("weekly.projection_observed_at",p,"missing observed_at")
            if x.get("reconciliation") not in {"read_time","explicit_reconciliation"}:self.error("weekly.projection_reconciliation",p,"invalid reconciliation")
            src=x.get("source_revisions")or[]
            if not isinstance(src,list) or not src:self.error("weekly.projection_sources",p,"missing sources");continue
            for s in src:
                if not isinstance(s,dict) or not s.get("ref") or not isinstance(s.get("revision"),int):self.error("weekly.projection_source",p,"invalid source");continue
                q=self.docs.get(s["ref"])
                if q is None:self.error("weekly.projection_source_missing",p,s["ref"])
                elif isinstance(q.get("revision"),int) and s["revision"]>q["revision"]:self.error("weekly.projection_source_future",p,s["ref"])
    def run(self):self.load();self.structural();self.refs();self.sequence();self.authority();self.weekly();return self.findings

# ===== V0.4 Core plane surface (authorized V0.4-B2-A) =====
# validate_core accepts a materialized Core snapshot directory and performs
# structural privacy/ownership boundary enforcement. It is deterministic and
# offline: GitHub state is never consulted. It is NOT complete secret
# detection; only structurally detectable credential/secrets cases fail closed.

CORE_SCHEMA="0.4"
CORE_ALLOWED_TOP={"config","protocol","domains","scripts","tests","docs",".github"}
CORE_ALLOWED_FILES={"README.md","requirements-dev.txt",".gitignore","LICENSE"}
CORE_PROHIBITED_TOP={"learner":"learner state","evidence":"evidence","topics":"topic execution state","execution":"execution state","coordination":"coordination state","runtime":"runtime state incl. private runtime/lineages control"}
CORE_CONFIG_FORBIDDEN={"project.yaml":"instance-authoritative project configuration","project-instructions.md":"instance-local instructions","project-ui-bootstrap.md":"instance-local UI bootstrap","deployment.yaml":"control-plane deployment binding","instance.yaml":"instance plane configuration"}
CORE_INSTANCE_DOC_TYPES={"lineage_control","branch_runtime","learning_handoff","conversation_sequence_registry","project_config","deployment_binding","migration_transaction","evidence","learner_background","learner_model","learner_calibration","learner_costs","learner_execution","learner_knowledge","topic_goal","topic_plan","topic_progress","topic_deferred","subtopic_definition","subtopic_plan","subtopic_progress","weekly_execution","daily_execution","execution_session","branch_registry","branch_report","coordination_event","hub_runtime","topic_report"}
CORE_PROHIBITED_KEYS={"deployment_epoch","active_deployment","write_state","active_deployed_commit","deployed_commit","deployed_core_commit","deployment_binding","migration_authorized","migration_authorization","active_generation","pending_handoff","lineage_control","repository_id","repository_full_name","instance_repository_id","instance_repository_full_name","core_repository_id","secret","secrets","token","tokens","password","api_key","api_token","private_key","credential","credentials"}
CORE_TOKEN_RE=re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{16,}\b")
CORE_FIXTURE_DIR="tests/fixtures"

class CoreValidator:
    """Deterministic validate_core(core_snapshot) surface for the V0.4 Core plane."""
    def __init__(self,root:Path): self.root=root.resolve(); self.findings=[]; self.yaml_docs={}; self.text_docs=[]
    def error(self,c,p,m): self.findings.append(Finding("error",c,p,m))
    def run(self):
        if not self.root.is_dir(): self.error("core.snapshot",".","core snapshot root is not a directory"); return self.findings
        self.scan_top(); self.collect(); self.check_documents(); self.check_core_config(); return self.findings
    def scan_top(self):
        for e in sorted(self.root.iterdir()):
            n=e.name
            if n==".git": continue
            if e.is_dir():
                if n in CORE_PROHIBITED_TOP:
                    code="core.private_lineage" if n=="runtime" else "core.plane"
                    self.error(code,n,f"Core snapshot must not contain {n}/ ({CORE_PROHIBITED_TOP[n]} belongs to Instance/Control planes)")
                elif n not in CORE_ALLOWED_TOP: self.error("core.top_level",n,f"unexpected top-level directory {n}/")
                if n=="config":
                    for f in sorted(e.iterdir()):
                        if f.name in CORE_CONFIG_FORBIDDEN: self.error("core.config_forbidden",f"config/{f.name}",CORE_CONFIG_FORBIDDEN[f.name])
                        elif f.name!="core.yaml": self.error("core.config_entry",f"config/{f.name}","only config/core.yaml is allowed in the Core config directory")
            elif n not in CORE_ALLOWED_FILES: self.error("core.top_level",n,f"unexpected top-level file {n}")
    def collect(self):
        for f in sorted(self.root.rglob("*.y*ml")):
            rp=f.relative_to(self.root); p=rp.as_posix()
            if rp.parts[0]==".git": continue
            try: d=yaml.safe_load(f.read_text(encoding="utf-8"))
            except Exception as e: self.yaml_docs[p]=None; self.error("core.yaml_parse",p,str(e)); continue
            if not isinstance(d,dict): self.yaml_docs[p]=None; self.error("core.yaml_mapping",p,"Core YAML must be a mapping")
            else: self.yaml_docs[p]=d
        # Markdown documents are scanned for credential material at text level.
        # tests/ may legitimately contain token patterns as test material.
        for f in sorted(self.root.rglob("*.md")):
            rp=f.relative_to(self.root)
            if rp.parts[0] in (".git","tests"): continue
            self.text_docs.append(f)
    def check_keys(self,p,d,fixture=False):
        def walk(x,path):
            if isinstance(x,dict):
                for k,v in x.items():
                    kp=f"{path}.{k}" if path else str(k)
                    if not fixture and k in CORE_PROHIBITED_KEYS: self.error("core.prohibited_key",f"{p}:{kp}",f"forbidden ownership/authority key: {k}")
                    walk(v,kp)
            elif isinstance(x,list):
                for i,v in enumerate(x): walk(v,f"{path}[{i}]")
            elif isinstance(x,str) and CORE_TOKEN_RE.search(x):
                self.error("core.credential_value",f"{p}:{path}","structurally detected credential/token value")
        walk(d,"")
    def check_documents(self):
        for p,d in self.yaml_docs.items():
            if d is None: continue
            # Synthetic fixtures and .github platform workflows are exempt
            # from document-type/ownership-key checks; credential values are
            # still rejected everywhere.
            fixture=p.startswith(CORE_FIXTURE_DIR+"/") or p.startswith(".github/")
            if fixture: self.check_keys(p,d,fixture=True); continue
            t=d.get("document_type")
            if t is None: self.error("core.document_type",p,"missing document_type")
            elif t in CORE_INSTANCE_DOC_TYPES: self.error("core.plane_document",p,f"{t} is Instance/Control plane material")
            self.check_keys(p,d)
        for f in self.text_docs:
            if CORE_TOKEN_RE.search(f.read_text(encoding="utf-8")):
                self.error("core.credential_value",f.relative_to(self.root).as_posix(),"structurally detected credential/token value in document text")
    def check_core_config(self):
        p="config/core.yaml"
        if p not in self.yaml_docs: self.error("core.config_missing",p,"config/core.yaml is required (fail closed)"); return
        d=self.yaml_docs[p]
        if d is None: return
        if d.get("schema_version")!=CORE_SCHEMA: self.error("core.schema_version",p,f"core contract requires schema_version {CORE_SCHEMA!r}")
        if d.get("document_type")!="core_config": self.error("core.document_type",p,"requires document_type core_config")
        prod=d.get("product") or {}
        if not (isinstance(prod.get("id"),str) and prod["id"].strip()): self.error("core.product_identity",p,"product.id must be a non-empty string")
        m=d.get("manifest") or {}
        if not (isinstance(m.get("release"),str) and m["release"].strip()): self.error("core.manifest_release",p,"manifest.release must be a non-empty string")
        if m.get("artifact_schema")!=CORE_SCHEMA: self.error("core.artifact_schema",p,f"manifest.artifact_schema must be {CORE_SCHEMA!r}")
        sv=m.get("supported_instance_schema_versions")
        if not (isinstance(sv,list) and sv and all(isinstance(x,str) and x for x in sv)): self.error("core.instance_schema_support",p,"manifest.supported_instance_schema_versions must be a non-empty string list")
        if m.get("canonical_status")!="noncanonical": self.error("core.canonical_status",p,"manifest.canonical_status must be noncanonical")
        if m.get("deployment_status")!="not_deployed": self.error("core.deployment_status",p,"manifest.deployment_status must be not_deployed; deployment-active values are forbidden")
        t=d.get("time") or {}
        if t.get("timestamp_format")!="iso8601": self.error("core.timestamp_format",p,"time.timestamp_format must be iso8601")
        if t.get("require_reliable_source") is not True: self.error("core.reliable_time",p,"time.require_reliable_source must be true")
        proto=d.get("protocol") or {}
        routed={v for v in proto.values() if isinstance(v,str)}
        for k,v in proto.items():
            if not isinstance(v,str) or not (self.root/v).is_file(): self.error("core.protocol_route",p,f"protocol.{k} -> missing file {v!r}")
        pdir=self.root/"protocol"
        if pdir.is_dir():
            for fmd in sorted(pdir.glob("*.md")):
                if f"protocol/{fmd.name}" not in routed: self.error("core.protocol_orphan",f"protocol/{fmd.name}","protocol document is not routed by config/core.yaml")
        g=(d.get("governance") or {}).get("core_mutation") or {}
        if g.get("model")!="pull_request_required": self.error("core.governance_model",p,"governance.core_mutation.model must be pull_request_required")
        dom=d.get("domains") or {}; bases=dom.get("reusable_bases")
        if not (isinstance(bases,list) and bases and all(isinstance(x,str) and x for x in bases)): self.error("core.domains_declared",p,"domains.reusable_bases must be a non-empty string list"); bases=[]
        ddir=self.root/"domains"; actual={x.name for x in ddir.iterdir() if x.is_dir()} if ddir.is_dir() else set()
        for extra in sorted(actual-set(bases)): self.error("core.domain_undeclared",f"domains/{extra}","domain base present in tree but not declared by config/core.yaml")
        for base in bases:
            if base not in actual: self.error("core.domain_declared_missing",f"domains/{base}","declared reusable base has no directory")
        self.check_domain_bases(sorted(set(bases)&actual))
        r=self.root/"README.md"
        if not r.is_file(): self.error("core.readme","README.md","Core README is required")
        else:
            text=r.read_text(encoding="utf-8")
            if "NONCANONICAL" not in text or "NOT DEPLOYED" not in text: self.error("core.status_marker","README.md","README must state NONCANONICAL and NOT DEPLOYED")
    def check_domain_bases(self,bases):
        for base in bases:
            p=f"domains/{base}/curriculum.yaml"; d=self.yaml_docs.get(p)
            if d is None: self.error("core.domain_document",p,"reusable base must contain a valid curriculum.yaml"); continue
            if d.get("document_type")!="curriculum": self.error("core.domain_document",p,"requires document_type curriculum"); continue
            if (d.get("domain") or {}).get("id")!=base: self.error("core.domain_identity",p,f"domain.id must be {base!r}")
            for k,x in (d.get("nodes") or {}).items():
                if isinstance(x,dict) and x.get("kind") not in NKIND: self.error("core.curriculum_enum",p,f"nodes.{k}.kind={x.get('kind')!r} not in {sorted(NKIND)}")
            for x in d.get("edges") or []:
                if isinstance(x,dict):
                    if x.get("relation") not in EREL: self.error("core.curriculum_enum",p,f"edge {x.get('id')!r} relation invalid")
                    if x.get("strength") not in ESTR: self.error("core.curriculum_enum",p,f"edge {x.get('id')!r} strength invalid")

def validate_core(core_snapshot):
    """V0.4 Core plane validation surface: validate_core(core_snapshot).

    Accepts a materialized Core snapshot path. Deterministic and offline;
    GitHub state is never consulted. Provides structural privacy/ownership
    boundary enforcement, not complete secret detection.
    """
    return CoreValidator(Path(core_snapshot)).run()

def main():
    a=argparse.ArgumentParser(description="Learning OS deterministic validator")
    a.add_argument("root",nargs="?",default=".")
    a.add_argument("--core",action="store_true",help="validate a materialized V0.4 Core plane snapshot (validate_core surface)")
    args=a.parse_args(); root=Path(args.root)
    if args.core: findings=validate_core(root); label="Core snapshot"
    else:
        v=Validator(root); findings=v.run(); label=f"{len(v.docs)} canonical YAML documents"
    for x in findings: print(x.render())
    e=[x for x in findings if x.severity=="error"]; print(f"validated {label}: {len(e)} error(s)"); return 1 if e else 0
if __name__=="__main__":raise SystemExit(main())
