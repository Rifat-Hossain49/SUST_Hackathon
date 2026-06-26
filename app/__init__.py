"""QueueStorm Investigator — AI/API SupportOps copilot.

A safe, evidence-grounded support copilot for a digital-finance campaign surge.
It reads one customer complaint plus a short transaction-history snippet, decides
which transaction the complaint refers to, judges whether the data supports the
complaint, classifies and routes the case, and drafts a safe customer reply.

Decisions are deterministic (rule-based) so they are reproducible and immune to
prompt injection. An optional LLM can polish the human-readable text, but the
safety filter is always the last word. See README.md for the full design.
"""
