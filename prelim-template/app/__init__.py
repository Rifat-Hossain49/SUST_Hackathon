"""Codex Hackathon preliminary-round API service template.

A safe, evidence-grounded "support copilot" API built to the bKash / SUST CSE
Carnival 2026 preliminary rubric. The example domain (transaction / support
case review) is a PLACEHOLDER: swap the schema in `schemas.py` and the policy
in `reasoning.py` for the official Problem Statement when it is released. The
plumbing — health endpoint, strict JSON contract, safety guardrails, graceful
error handling, optional LLM augmentation, Docker — is the reusable part.
"""

__version__ = "0.1.0"
