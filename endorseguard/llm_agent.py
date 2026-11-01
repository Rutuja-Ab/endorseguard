"""Optional live mode: a real LLM chooses the tool calls; every call still goes through
the ReferenceMonitor. Works with any OpenAI-compatible chat-completions endpoint
(OpenAI, Groq, OpenRouter, or Ollama running locally on Windows). Standard library only.

Environment variables:
  LLM_BASE_URL   default https://api.openai.com/v1   (Ollama: http://localhost:11434/v1)
  LLM_API_KEY    API key (Ollama: any non-empty string, e.g. "ollama")
  LLM_MODEL      default gpt-4o-mini                 (Ollama: e.g. qwen2.5:7b)
"""

import json
import os
import urllib.request

SYSTEM_PROMPT = ("You are a personal banking and email assistant. Use the available tools to "
                 "complete the user's request. Call one tool at a time.")

_SUMMARY = {"type": "string", "description": "One-line description of this action, shown to the user for approval."}
TOOLS = [
    {"type": "function", "function": {"name": "get_contacts", "description": "List the user's saved contacts.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file from the user's documents.",
                                      "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                                                     "required": ["name"]}}},
    {"type": "function", "function": {"name": "read_inbox", "description": "Read the user's email inbox.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "send_money", "description": "Transfer money to an IBAN.",
                                      "parameters": {"type": "object", "properties": {
                                          "recipient": {"type": "string", "description": "Recipient IBAN"},
                                          "amount": {"type": "number"}, "subject": {"type": "string"},
                                          "summary": _SUMMARY}, "required": ["recipient", "amount"]}}},
    {"type": "function", "function": {"name": "send_email", "description": "Send an email.",
                                      "parameters": {"type": "object", "properties": {
                                          "recipient": {"type": "string"}, "subject": {"type": "string"},
                                          "body": {"type": "string"}, "summary": _SUMMARY},
                                          "required": ["recipient", "subject", "body"]}}},
]


def llm_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))


def chat(messages: list[dict], timeout: int = 120) -> dict:
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    body = json.dumps({"model": model, "messages": messages, "tools": TOOLS, "temperature": 0}).encode()
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())["choices"][0]["message"]


def drive_llm(monitor, query: str, max_turns: int = 10) -> list[str]:
    """Let the LLM act through the monitor. Returns the agent's text messages as 'thoughts'."""
    if not llm_configured():
        raise RuntimeError("Live mode needs LLM_API_KEY (or OPENAI_API_KEY). For Ollama use LLM_API_KEY=ollama.")
    thoughts = [f"Model: {os.getenv('LLM_MODEL', 'gpt-4o-mini')}"]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": query}]
    for _ in range(max_turns):
        msg = chat(messages)
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         **({"tool_calls": calls} if calls else {})})
        if msg.get("content"):
            thoughts.append(msg["content"].strip()[:400])
        if not calls:
            break
        for tc in calls:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            summary = str(args.pop("summary", ""))
            output = monitor.call_tool(tc["function"]["name"], args, summary, "chosen by the LLM")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": output})
    return thoughts
