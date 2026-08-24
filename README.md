# Learning OS — Core

Status: NONCANONICAL V0.4 CANDIDATE — NOT DEPLOYED

This repository is the candidate Core plane for the Learning OS V0.4
separation architecture. It is a staging target only and has no current
production authority.

Canonical production remains:

suxyddjdgys-arch/learning-os
release 0.3.2
topology LEGACY

The Core plane owns reusable product semantics only: the Core contract
(`config/core.yaml`, schema 0.4), protocol documents, the deterministic
validator (`validate_core`), synthetic tests, and stable reusable domain
templates. It contains no learner state, no Evidence, no Instance or
deployment authority, and no credentials. All test fixtures are synthetic.

Validation (offline, deterministic):

    python scripts/validate_learning_os.py . --core
    python -m unittest discover -s tests -v

Core mutation follows PR-required governance. This repository is not part
of any Runtime installation and is not read by any deployed runtime.
