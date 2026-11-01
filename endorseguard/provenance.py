"""Provenance tracking by value matching (mode "P2" in the roadmap).

Every tool output the agent reads is logged with its source and control domain.
When the agent proposes a write call, the guarded argument is labelled:
  * trusted        - value comes from the user's own request or a trusted store (contacts)
  * untrusted      - value only appears in data the agent read (files, emails)
plus extra facts used by the stricter strategies (look-alike contact, named payee)."""

import re
from dataclasses import dataclass, field

from .canonical import canonical, find_values, has_non_ascii, skeleton
from .environment import World


@dataclass
class Source:
    source_id: str      # e.g. "file:bill-water.txt", "email:billing@x.com"
    domain: str         # who controls the content
    text: str


@dataclass
class Label:
    value: str
    kind: str
    raw_trusted: bool                 # exact raw string equals a trusted value (naive check)
    trusted: bool                     # canonical form equals a trusted value
    trusted_match: str | None         # which trusted entry matched
    raw_sources: list[Source] = field(default_factory=list)        # raw substring match
    sources: list[Source] = field(default_factory=list)            # canonical match
    lookalike_of: str | None = None   # looks like a contact's value but is different
    named_contacts: dict[str, str] = field(default_factory=dict)  # contacts the user referred to

    @property
    def domains(self) -> set[str]:
        return {s.domain for s in self.sources}


class ProvenanceTracker:
    def __init__(self, user_query: str, world: World):
        self.user_query = user_query
        self.world = world
        self.log: list[Source] = []

    def record(self, source_id: str, domain: str, text: str) -> None:
        self.log.append(Source(source_id, domain, text))

    def _trusted_values(self, kind: str) -> dict[str, str]:
        """canonical value -> description, from the user query and the contact list."""
        out = {v: "user request" for v in find_values(self.user_query, kind)}
        for c in self.world.contacts.values():
            v = c.iban if kind == "iban" else c.email
            if v:
                out[canonical(v, kind)] = f"contact '{c.name}'"
        return out

    def named_contacts(self, kind: str) -> dict[str, str]:
        """Contacts the user referred to by name ("my landlord") -> their canonical value."""
        q = self.user_query.lower()
        out = {}
        for c in self.world.contacts.values():
            v = c.iban if kind == "iban" else c.email
            if v and any(re.search(rf"\b{re.escape(a)}", q) for a in c.aliases):
                out[c.name] = canonical(v, kind)
        return out

    def label(self, value: str, kind: str) -> Label:
        trusted = self._trusted_values(kind)
        raw_trusted_values = set(find_values(self.user_query, kind)) | {
            (c.iban if kind == "iban" else c.email) for c in self.world.contacts.values()}
        canon = canonical(value, kind)
        label = Label(
            value=value, kind=kind,
            raw_trusted=value in raw_trusted_values,
            trusted=canon in trusted,
            trusted_match=trusted.get(canon),
        )
        for src in self.log:
            if value in src.text:
                label.raw_sources.append(src)
            if canon in find_values(src.text, kind) or canon in canonical(src.text, kind):
                label.sources.append(src)
        if not label.trusted:
            for tv, desc in trusted.items():
                if skeleton(tv, kind) == skeleton(canon, kind) or (
                        has_non_ascii(value) and skeleton(value, kind) == skeleton(tv, kind)):
                    label.lookalike_of = f"{tv} ({desc})"
                    break
        label.named_contacts = self.named_contacts(kind)
        return label
