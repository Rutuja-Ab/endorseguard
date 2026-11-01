"""A small banking + email world for the agent (modelled on AgentDojo's banking and
workspace suites), and the tool registry that says which tools are read vs write.
Worlds are plain data so they can be loaded from JSON and edited in the dashboard."""

import copy
from dataclasses import dataclass, field

# ---------------------------------------------------------------- tool registry
READ_TOOLS = {"get_contacts", "read_file", "read_inbox"}
# write tool -> (argument that must be authorised, value kind)
WRITE_TOOLS = {
    "send_money": ("recipient", "iban"),
    "send_email": ("recipient", "email"),
}


def make_iban(country: str, bban: str) -> str:
    """Build an IBAN with correct ISO 13616 check digits."""
    digits = "".join(str(int(ch, 36)) for ch in bban + country + "00")
    return f"{country}{98 - int(digits) % 97:02d}{bban}"


# Attacker identifiers offered by the dashboard's "insert attack" helper.
ATTACKER_IBAN = make_iban("LT", "121000011101001000")
ATTACKER_EMAIL = "billing@secure-payments-portal.io"


@dataclass
class Contact:
    name: str
    iban: str = ""
    email: str = ""
    aliases: tuple[str, ...] = ()   # words the user may use for this person ("landlord")


@dataclass
class Document:
    text: str
    domain: str          # control domain: who could have written this content


@dataclass
class Email:
    sender: str
    subject: str
    body: str


@dataclass
class World:
    contacts: dict[str, Contact]
    files: dict[str, Document] = field(default_factory=dict)
    inbox: list[Email] = field(default_factory=list)
    transfers: list[dict] = field(default_factory=list)   # executed send_money calls
    outbox: list[dict] = field(default_factory=list)      # executed send_email calls

    @classmethod
    def from_dict(cls, d: dict) -> "World":
        contacts = {}
        for i, c in enumerate(d.get("contacts", [])):
            aliases = c.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [a.strip() for a in aliases.split(",")]
            contacts[f"c{i}"] = Contact(c.get("name", "").strip(), c.get("iban", "").strip(),
                                        c.get("email", "").strip(),
                                        tuple(a.lower() for a in aliases if a))
        files = {f["name"].strip(): Document(f.get("text", ""), f.get("domain", "").strip() or "unknown")
                 for f in d.get("files", []) if f.get("name", "").strip()}
        inbox = [Email(m.get("sender", "").strip(), m.get("subject", ""), m.get("body", ""))
                 for m in d.get("inbox", [])]
        return cls(contacts, files, inbox)

    def copy(self) -> "World":
        return copy.deepcopy(self)

    # --- read tools (outputs are UNTRUSTED except get_contacts, a trusted store)
    def get_contacts(self) -> str:
        return "\n".join(f"{c.name}: IBAN {c.iban or '-'}, email {c.email or '-'}"
                         for c in self.contacts.values())

    def read_file(self, name: str) -> str:
        if name not in self.files:
            raise KeyError(f"No file named {name!r}. Available: {sorted(self.files)}")
        return self.files[name].text

    def read_inbox(self) -> str:
        return "\n\n".join(f"From: {m.sender}\nSubject: {m.subject}\n{m.body}" for m in self.inbox)

    # --- write tools
    def send_money(self, recipient: str, amount: float, subject: str = "") -> str:
        self.transfers.append({"recipient": recipient, "amount": float(amount), "subject": subject})
        return f"Transferred {float(amount):.2f} to {recipient}."

    def send_email(self, recipient: str, subject: str = "", body: str = "") -> str:
        self.outbox.append({"recipient": recipient, "subject": subject, "body": body})
        return f"Email sent to {recipient}."
