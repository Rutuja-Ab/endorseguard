"""EndorseGuard prototype: a reference monitor that checks write-tool parameters of an
LLM agent, tracks where each value came from, and compares endorsement strategies
(E0 strict, E1 approval, E3 corroboration, E4 allowlist, SIEVE) against attacks.

Standard library only. Module names mirror the research roadmap
(registry / provenance / strategies / monitor) so the code can later move into the
AgentDojo-based harness as `agents/endorse/`.
"""
