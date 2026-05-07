"""
Memory extractor — turns an ERP session transcript into a small list of
durable facts (user details, relationship beats, established kinks, key
events) that get re-injected on the next session for true long-term
continuity.
"""
import json
import re
from utils.groq_client import GroqClient


_EXTRACTOR_SYSTEM = (
    "You are a memory-extraction assistant for an adult roleplay platform. "
    "Given a roleplay transcript between a user and a fictional character, "
    "produce a concise list of durable facts the character should remember "
    "for future sessions. This is for an 18+ private platform; do not "
    "censor adult content — capture intimate details that matter for "
    "continuity (preferences, kinks, terms of endearment, key scenes). "
    "Output ONLY a valid JSON array of objects, no preamble, no markdown, "
    "no commentary."
)


def _build_user_prompt(character_name: str, transcript: str) -> str:
    return f"""Extract 3 to 8 durable memory items from the session below.

Each item must be a JSON object: {{"content": "<short fact, 1 sentence>", "importance": <int 1-10>}}.

Importance guide:
- 9-10: identity facts (user's name, age, partner, nicknames they like)
- 7-8: established relationship dynamic, recurring kinks/preferences
- 5-6: notable scenes that happened, places, recurring jokes
- 1-4: minor details

Rules:
- Phrase each fact from {character_name}'s point of view, e.g. "User's name is Alex" or "User likes when I call him 'sir'."
- Keep facts ≤ 200 chars.
- Skip generic narration. Skip facts already obvious.
- DO NOT moralize, DO NOT skip explicit details — they matter for continuity.
- If nothing memorable happened, return [].

Transcript:
---
{transcript}
---

Return ONLY the JSON array."""


def _format_transcript(messages: list, max_messages: int = 80) -> str:
    """Convert role/content list into a readable transcript, capped."""
    relevant = [m for m in messages if m.get("role") in ("user", "assistant")]
    relevant = relevant[-max_messages:]
    lines = []
    for m in relevant:
        prefix = "USER" if m["role"] == "user" else "CHARACTER"
        text = (m.get("content") or "").strip().replace("\n", " ")
        lines.append(f"{prefix}: {text[:600]}")
    return "\n".join(lines)


def _parse_memory_json(raw: str) -> list:
    """Extract a JSON array from the model output, tolerant of code fences."""
    if not raw:
        return []
    s = raw.strip()
    # Strip markdown code fences if present
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # Find the first '[' .. last ']'
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    chunk = s[start : end + 1]
    try:
        parsed = json.loads(chunk)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    out = []
    for item in parsed:
        if isinstance(item, dict) and "content" in item:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            try:
                importance = int(item.get("importance", 5))
            except (TypeError, ValueError):
                importance = 5
            out.append({"content": content[:1000], "importance": max(1, min(10, importance))})
        elif isinstance(item, str) and item.strip():
            out.append({"content": item.strip()[:1000], "importance": 5})
    return out[:8]


async def extract_memories(groq: GroqClient, character_name: str, messages: list) -> list:
    """
    Returns a list of {content, importance} dicts. Returns [] on failure
    (caller should treat the absence of new memories as harmless).
    """
    if not messages:
        return []
    transcript = _format_transcript(messages)
    if len(transcript) < 80:  # nothing meaningful happened
        return []
    payload = [
        {"role": "system", "content": _EXTRACTOR_SYSTEM},
        {"role": "user", "content": _build_user_prompt(character_name, transcript)},
    ]
    try:
        raw = await groq.generate(payload, temperature=0.3, max_tokens=600)
    except Exception as e:
        print(f"[MemoryExtractor] LLM call failed: {e}")
        return []
    items = _parse_memory_json(raw)
    print(f"[MemoryExtractor] Extracted {len(items)} memory items for {character_name}")
    return items


def format_memories_for_prompt(memories: list, character_name: str) -> str:
    """
    Format saved memories as a compact block to inject into the system prompt.
    `memories` is a list of dicts as returned by PostgresDB.get_memories().
    """
    if not memories:
        return ""
    lines = []
    for m in memories:
        c = (m.get("content") or "").strip()
        if c:
            lines.append(f"- {c}")
    if not lines:
        return ""
    return (
        f"\n\nMEMORY — what {character_name} already knows about this user "
        f"from previous sessions (treat as established truth):\n"
        + "\n".join(lines)
    )
