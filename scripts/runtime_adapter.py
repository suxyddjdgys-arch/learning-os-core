"""V0.4 live resolver and guarded Instance mutation adapter.

The validator remains deterministic and offline. This module performs the
live/materialization duties that intentionally do not belong to it.
"""
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Protocol

import yaml

from scripts.validate_learning_os import RepositorySnapshot, validate_deployment

EXACT_COMMIT = re.compile(r"[0-9a-f]{40}")


class ResolutionError(RuntimeError):
    pass


class GuardRejected(RuntimeError):
    pass


class CasConflict(RuntimeError):
    pass


class TransitionRejected(RuntimeError):
    pass


@dataclass(frozen=True)
class MaterializedRepository:
    root: Path
    repository_id: int
    commit_sha: str
    full_name: str = ""


@dataclass(frozen=True)
class SessionDeploymentContext:
    deployment_id: str
    epoch: int
    core_repository_id: int
    core_commit: str
    instance_repository_id: int
    runtime_control_repository_id: int
    runtime_control_ref: str
    contract_path: str


@dataclass
class ResolvedDeployment:
    context: SessionDeploymentContext
    control: MaterializedRepository
    core: MaterializedRepository
    instance: MaterializedRepository


class RepositoryProvider(Protocol):
    def materialize(self, repository_id: int, ref: str) -> MaterializedRepository: ...
    def read_text(self, repository_id: int, ref: str, path: str) -> tuple[str, str, str]: ...
    def update_text(self, repository_id: int, branch: str, path: str, content: str,
                    expected_blob_sha: str, message: str) -> str: ...


def _positive_id(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ResolutionError(f"{where} must be a positive numeric repository ID")
    return value


def _nonempty(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResolutionError(f"{where} must be a non-empty string")
    return value


def load_locator(source: str | Path | dict) -> dict:
    if isinstance(source, dict):
        data = source
    else:
        try:
            data = yaml.safe_load(Path(source).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ResolutionError(f"trusted locator is unreadable: {exc.__class__.__name__}") from None
    allowed_top = {"schema_version", "document_type", "runtime_control", "instance"}
    if not isinstance(data, dict) or set(data) - allowed_top:
        raise ResolutionError("trusted locator contains unknown top-level fields")
    if not {"runtime_control", "instance"} <= set(data):
        raise ResolutionError("trusted locator requires runtime_control and instance")
    if data.get("schema_version", "0.4") != "0.4":
        raise ResolutionError("trusted locator schema_version must be '0.4'")
    if data.get("document_type", "trusted_locator") != "trusted_locator":
        raise ResolutionError("trusted locator document_type must be trusted_locator")
    rc, inst = data["runtime_control"], data["instance"]
    if not isinstance(rc, dict) or not isinstance(inst, dict):
        raise ResolutionError("trusted locator sections must be mappings")
    rc_allowed = {"repository_id", "repository", "canonical_ref", "contract_path"}
    inst_allowed = {"repository_id", "repository", "canonical_ref"}
    if set(rc) - rc_allowed or set(inst) - inst_allowed:
        raise ResolutionError("trusted locator contains unknown fields")
    return {
        "runtime_control": {
            **rc,
            "repository_id": _positive_id(rc.get("repository_id"), "runtime_control.repository_id"),
            "canonical_ref": _nonempty(rc.get("canonical_ref", "main"), "runtime_control.canonical_ref"),
            "contract_path": _nonempty(rc.get("contract_path", "deployment.yaml"), "runtime_control.contract_path"),
        },
        "instance": {
            **inst,
            "repository_id": _positive_id(inst.get("repository_id"), "instance.repository_id"),
            "canonical_ref": _nonempty(inst.get("canonical_ref", "main"), "instance.canonical_ref"),
        },
    }


def _load_contract(text: str) -> dict:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ResolutionError(f"Runtime-Control contract is malformed YAML: {exc.__class__.__name__}") from None
    if not isinstance(data, dict):
        raise ResolutionError("Runtime-Control contract must be a mapping")
    deployment, core = data.get("deployment"), data.get("core")
    if not isinstance(deployment, dict) or not isinstance(core, dict):
        raise ResolutionError("Runtime-Control deployment/core sections must be mappings")
    return data


def validate_initial_cutover(contract: dict) -> None:
    """Validate the unique LEGACY -> SPLIT semantic cutover contract."""
    dep = contract.get("deployment") if isinstance(contract, dict) else None
    core = contract.get("core") if isinstance(contract, dict) else None
    if not isinstance(dep, dict) or not isinstance(core, dict):
        raise TransitionRejected("initial cutover contract is malformed")
    if dep.get("topology") != "split" or dep.get("write_state") != "frozen":
        raise TransitionRejected("initial split cutover must publish frozen")
    if dep.get("epoch") != 1:
        raise TransitionRejected("initial split cutover epoch must be 1")
    if not isinstance(core.get("repository_id"), int) or not EXACT_COMMIT.fullmatch(str(core.get("commit", ""))):
        raise TransitionRejected("initial split cutover requires an exact Core identity and pin")


def validate_deployment_transition(previous: dict, current: dict) -> None:
    """Validate one Runtime-Control transition independently of snapshots."""
    try:
        pdep, pcore = previous["deployment"], previous["core"]
        cdep, ccore = current["deployment"], current["core"]
    except (KeyError, TypeError):
        raise TransitionRejected("transition contracts are malformed") from None
    if pdep.get("id") != cdep.get("id"):
        raise TransitionRejected("deployment id is immutable")
    if pdep.get("topology") != "split" or cdep.get("topology") != "split":
        raise TransitionRejected("Runtime-Control history is split-only")
    if pcore.get("repository_id") != ccore.get("repository_id"):
        raise TransitionRejected("Core repository identity is immutable within a deployment")
    pe, ce = pdep.get("epoch"), cdep.get("epoch")
    if not isinstance(pe, int) or not isinstance(ce, int) or ce < pe:
        raise TransitionRejected("deployment epoch must never decrease")
    pin_changed = pcore.get("commit") != ccore.get("commit")
    if pin_changed:
        if pdep.get("write_state") != "frozen" or cdep.get("write_state") != "frozen":
            raise TransitionRejected("Core promotion requires frozen -> frozen")
        if ce != pe + 1:
            raise TransitionRejected("Core promotion must increment epoch exactly once")
        if not EXACT_COMMIT.fullmatch(str(ccore.get("commit", ""))):
            raise TransitionRejected("promoted Core pin must be exact")
    elif ce != pe:
        raise TransitionRejected("epoch changes only with an exact Core promotion")
    allowed_states = {("active", "frozen"), ("frozen", "active"),
                      ("active", "active"), ("frozen", "frozen")}
    if (pdep.get("write_state"), cdep.get("write_state")) not in allowed_states:
        raise TransitionRejected("invalid write-state transition")


def pointer_rollback_allowed(*, post_cutover_instance_mutated: bool) -> bool:
    return not post_cutover_instance_mutated


class DeploymentResolver:
    def __init__(self, provider: RepositoryProvider):
        self.provider = provider

    def resolve(self, locator_source: str | Path | dict) -> ResolvedDeployment:
        locator = load_locator(locator_source)
        rc, inst = locator["runtime_control"], locator["instance"]
        control = self.provider.materialize(rc["repository_id"], rc["canonical_ref"])
        if control.repository_id != rc["repository_id"]:
            raise ResolutionError("resolved Runtime-Control repository ID mismatch")
        contract_text, _, _ = self.provider.read_text(
            rc["repository_id"], rc["canonical_ref"], rc["contract_path"]
        )
        contract = _load_contract(contract_text)
        core_block = contract["core"]
        core_id = _positive_id(core_block.get("repository_id"), "core.repository_id")
        core_commit = _nonempty(core_block.get("commit"), "core.commit")
        if not EXACT_COMMIT.fullmatch(core_commit):
            raise ResolutionError("core.commit must be an exact 40-lowercase-hex commit")
        core = self.provider.materialize(core_id, core_commit)
        if core.repository_id != core_id or core.commit_sha != core_commit:
            raise ResolutionError("resolved Core provenance does not match the exact deployment pin")
        instance = self.provider.materialize(inst["repository_id"], inst["canonical_ref"])
        if instance.repository_id != inst["repository_id"]:
            raise ResolutionError("resolved Instance repository ID mismatch")
        findings = validate_deployment(
            RepositorySnapshot(control.root, control.repository_id, control.commit_sha),
            RepositorySnapshot(core.root, core.repository_id, core.commit_sha),
            RepositorySnapshot(instance.root, instance.repository_id, instance.commit_sha),
            locator,
        )
        errors = [finding.render() for finding in findings if finding.severity == "error"]
        if errors:
            raise ResolutionError("deployment validation failed:\n" + "\n".join(errors))
        dep = contract["deployment"]
        epoch = dep.get("epoch")
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 1:
            raise ResolutionError("deployment.epoch must be a positive integer")
        context = SessionDeploymentContext(
            deployment_id=_nonempty(dep.get("id"), "deployment.id"),
            epoch=epoch,
            core_repository_id=core_id,
            core_commit=core_commit,
            instance_repository_id=inst["repository_id"],
            runtime_control_repository_id=rc["repository_id"],
            runtime_control_ref=rc["canonical_ref"],
            contract_path=rc["contract_path"],
        )
        return ResolvedDeployment(context, control, core, instance)


class DeploymentGuard:
    def __init__(self, provider: RepositoryProvider):
        self.provider = provider

    def check(self, session: SessionDeploymentContext) -> dict:
        try:
            text, _, _ = self.provider.read_text(
                session.runtime_control_repository_id,
                session.runtime_control_ref,
                session.contract_path,
            )
            contract = _load_contract(text)
        except (ResolutionError, OSError, RuntimeError) as exc:
            raise GuardRejected(f"Runtime-Control fresh-read failed closed: {exc}") from None
        dep, core = contract["deployment"], contract["core"]
        for ok, message in (
            (dep.get("write_state") == "active", "deployment is not active"),
            (dep.get("id") == session.deployment_id, "deployment id changed"),
            (dep.get("epoch") == session.epoch, "deployment epoch changed"),
            (core.get("repository_id") == session.core_repository_id, "Core repository changed"),
            (core.get("commit") == session.core_commit, "Core commit changed"),
        ):
            if not ok:
                raise GuardRejected(message)
        return contract

    def guarded_update(
        self,
        session: SessionDeploymentContext,
        *,
        branch: str,
        path: str,
        content: str,
        expected_blob_sha: str,
        message: str,
        expected_generation: int | None = None,
        generation_reader: Callable[[], int] | None = None,
    ) -> str:
        self.check(session)
        if expected_generation is not None:
            if generation_reader is None:
                raise GuardRejected("generation guard input is missing")
            if generation_reader() != expected_generation:
                raise GuardRejected("semantic generation changed")
        try:
            return self.provider.update_text(
                session.instance_repository_id, branch, path, content,
                expected_blob_sha, message,
            )
        except CasConflict:
            raise
        except Exception as exc:
            raise CasConflict(f"target blob CAS failed: {exc}") from None


class GitHubApiProvider:
    """GitHub REST materializer and Instance CAS writer."""
    def __init__(self, token: str | None = None, api_url: str = "https://api.github.com"):
        self.token = token or os.environ.get("LEARNING_OS_GITHUB_TOKEN")
        self.api_url = api_url.rstrip("/")
        self._tempdirs: list[tempfile.TemporaryDirectory] = []

    def close(self) -> None:
        while self._tempdirs:
            self._tempdirs.pop().cleanup()

    def _request(self, method: str, path: str, payload: dict | None = None) -> object:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.api_url + path, data=body, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "learning-os-v0.4-runtime")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (409, 412, 422):
                raise CasConflict(f"GitHub rejected compare-and-swap ({exc.code})") from None
            raise ResolutionError(f"GitHub request failed ({exc.code})") from None
        except (urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise ResolutionError(f"GitHub request failed: {exc.__class__.__name__}") from None

    def _repo(self, repository_id: int) -> dict:
        data = self._request("GET", f"/repositories/{repository_id}")
        if not isinstance(data, dict) or data.get("id") != repository_id:
            raise ResolutionError("GitHub repository numeric identity mismatch")
        return data

    def _commit(self, full_name: str, ref: str) -> str:
        quoted = urllib.parse.quote(ref, safe="")
        data = self._request("GET", f"/repos/{full_name}/commits/{quoted}")
        sha = data.get("sha") if isinstance(data, dict) else None
        if not isinstance(sha, str) or not EXACT_COMMIT.fullmatch(sha):
            raise ResolutionError("GitHub did not return an exact commit")
        return sha

    @staticmethod
    def _safe_output(root: Path, repository_path: str) -> Path:
        pure = PurePosixPath(repository_path)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise ResolutionError("repository tree contains an unsafe path")
        output = root.joinpath(*pure.parts)
        output.parent.mkdir(parents=True, exist_ok=True)
        return output

    def materialize(self, repository_id: int, ref: str) -> MaterializedRepository:
        repo = self._repo(repository_id)
        full_name = _nonempty(repo.get("full_name"), "repository.full_name")
        commit = self._commit(full_name, ref)
        tree = self._request("GET", f"/repos/{full_name}/git/trees/{commit}?recursive=1")
        if not isinstance(tree, dict) or tree.get("truncated") is True:
            raise ResolutionError("GitHub tree is unavailable or truncated")
        td = tempfile.TemporaryDirectory(prefix="learning-os-snapshot-")
        self._tempdirs.append(td)
        root = Path(td.name)
        for entry in tree.get("tree", []):
            if not isinstance(entry, dict) or entry.get("type") != "blob":
                continue
            if entry.get("mode") != "100644":
                raise ResolutionError("snapshot contains a symlink, submodule, or executable blob")
            blob = self._request("GET", f"/repos/{full_name}/git/blobs/{entry.get('sha')}")
            if not isinstance(blob, dict) or blob.get("encoding") != "base64":
                raise ResolutionError("GitHub blob encoding is unsupported")
            try:
                content = base64.b64decode(blob["content"], validate=False)
            except (KeyError, TypeError, ValueError):
                raise ResolutionError("GitHub blob content is malformed") from None
            self._safe_output(root, _nonempty(entry.get("path"), "tree.path")).write_bytes(content)
        return MaterializedRepository(root, repository_id, commit, full_name)

    def read_text(self, repository_id: int, ref: str, path: str) -> tuple[str, str, str]:
        repo = self._repo(repository_id)
        full_name = _nonempty(repo.get("full_name"), "repository.full_name")
        quoted_path = urllib.parse.quote(path, safe="/")
        quoted_ref = urllib.parse.quote(ref, safe="")
        data = self._request("GET", f"/repos/{full_name}/contents/{quoted_path}?ref={quoted_ref}")
        if not isinstance(data, dict) or data.get("encoding") != "base64":
            raise ResolutionError("GitHub content response is malformed")
        try:
            text = base64.b64decode(data["content"]).decode("utf-8")
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise ResolutionError("GitHub content is not valid UTF-8") from None
        return text, _nonempty(data.get("sha"), "content.sha"), self._commit(full_name, ref)

    def update_text(self, repository_id: int, branch: str, path: str, content: str,
                    expected_blob_sha: str, message: str) -> str:
        repo = self._repo(repository_id)
        full_name = _nonempty(repo.get("full_name"), "repository.full_name")
        quoted_path = urllib.parse.quote(path, safe="/")
        data = self._request("PUT", f"/repos/{full_name}/contents/{quoted_path}", {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "sha": expected_blob_sha,
            "branch": branch,
        })
        commit = data.get("commit") if isinstance(data, dict) else None
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str) or not EXACT_COMMIT.fullmatch(sha):
            raise CasConflict("GitHub update returned no exact commit")
        return sha
