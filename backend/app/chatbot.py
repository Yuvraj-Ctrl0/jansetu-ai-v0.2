"""JanSetu Sahayak — retrieval-augmented chatbot over the verified scheme database.

Pipeline
  1. Redact sensitive identifiers (Aadhaar / account numbers) from the user's message.
  2. Retrieve the most relevant schemes (TF-IDF + name/abbreviation matching). For
     "which schemes am I eligible for?" questions with a profile, run the rule engine instead.
  3. Ground the LLM with ONLY those scheme records (+ the user's preliminary screening).
  4. Call the configured provider (Gemini or any OpenAI-compatible API).
  5. If no provider is configured or the call fails, build a deterministic answer from
     the same records ("offline mode") so the feature always works in demos.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request

from .engine import (OCCUPATIONS, AREAS, MARITAL_STATUSES, STUDENT_LEVELS, evaluate, format_inr,
                     rank_schemes, screen_all)

log = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1000
MAX_HISTORY = 8
TOP_K = 5

SYSTEM_PROMPT = """You are "JanSetu Sahayak", the helpful assistant inside JanSetu AI — a citizen app that helps people in India discover government welfare schemes and understand eligibility.

Follow these rules strictly:
1. For any scheme-specific fact (eligibility, benefit amounts, documents, how to apply, deadlines) use ONLY the information in SCHEME CONTEXT. If the answer is not there, say you do not have verified details and suggest the official portal or https://www.myscheme.gov.in. Never invent amounts, dates or criteria.
2. Never promise eligibility or approval. Say "you may be eligible" and suggest the app's "Check Eligibility" tool for a rule-by-rule check. Mention that final decisions are made by the official authority.
3. Be concise and easy to read: short sentences, bullet points, **bold** scheme names. Aim for under 170 words unless the user asks for more detail.
4. Reply in the same language and script as the user's latest message (English, Hindi, Hinglish, Marathi, etc.).
5. Never ask for Aadhaar numbers, bank account numbers, OTPs or passwords. If relevant, warn that applying for government schemes is free on official portals/CSCs and no one should ask for payment or OTPs over phone.
6. If USER PROFILE / PRELIMINARY SCREENING is provided, use it to personalise the answer, but tell the user which details are still missing when that matters.
7. If the question is unrelated to government schemes or public services, politely say you can help with schemes and offer an example question.
8. When you recommend a scheme, include its official link once (plain URL)."""

_INTENTS = {
    "documents": ("document", "papers", "kagaz", "kaagaz", "dastavej", "दस्तावेज", "proof", "certificate"),
    "apply": ("apply", "application", "register", "registration", "how to get", "kaise", "आवेदन", "avedan",
              "enrol", "enroll", "where to", "kahan"),
    "eligibility": ("eligib", "qualify", "who can", "can i get", "am i", "patra", "पात्र", "yogya", "योग्य"),
    "benefits": ("benefit", "amount", "how much", "kitna", "kitne", "paisa", "money", "लाभ", "labh", "₹", "rupees"),
}
_PERSONAL_MATCH = ("for me", "my profile", "i am eligible", "am i eligible", "which schemes", "what schemes",
                   "schemes can i", "mere liye", "मेरे लिए", "kaun si yojana", "कौन सी योजना", "suggest",
                   "recommend", "eligible for")
_GREETINGS = {"hi", "hello", "hey", "namaste", "namaskar", "नमस्ते", "hii", "helo", "good morning", "good evening"}
_LIST_WORDS = ("which scheme", "what scheme", "schemes", "list", "options", "kaun", "कौन", "yojanaye", "योजनाएं",
               "योजनाओं", "all ")

# Bilingual retrieval: Hindi / Hinglish keywords -> English search terms (query expansion).
QUERY_EXPANSIONS = {
    "घर": "house housing awas", "मकान": "house housing", "आवास": "housing awas", "किसान": "farmer kisan",
    "खेती": "farming farmer crop", "फसल": "crop insurance", "पेंशन": "pension", "विधवा": "widow pension",
    "बुजुर्ग": "senior citizen old age", "वृद्ध": "old age pension", "छात्रवृत्ति": "scholarship",
    "छात्र": "student scholarship", "पढ़ाई": "education student", "शिक्षा": "education", "लोन": "loan",
    "ऋण": "loan", "कर्ज": "loan", "बीमा": "insurance", "इलाज": "health hospital treatment",
    "अस्पताल": "hospital health", "स्वास्थ्य": "health", "राशन": "ration food", "अनाज": "foodgrain ration",
    "गैस": "lpg gas", "सिलेंडर": "lpg cylinder", "बिजली": "electricity solar", "सोलर": "solar rooftop",
    "नौकरी": "job employment", "रोजगार": "employment job", "महिला": "women", "बहन": "women", "बेटी": "daughter girl child",
    "गर्भवती": "pregnancy maternity", "प्रसव": "delivery maternity", "मजदूर": "worker labour unorganised",
    "श्रमिक": "worker labour", "व्यापार": "business loan", "दुकान": "shop business", "ठेला": "street vendor",
    "दिव्यांग": "disability", "विकलांग": "disability", "कौशल": "skill training", "प्रशिक्षण": "training skill",
    "इंटर्नशिप": "internship", "खाता": "bank account", "दस्तावेज": "documents", "आवेदन": "apply",
    "ghar": "house housing", "makaan": "house", "kisan": "farmer", "kheti": "farming farmer", "naukri": "job employment",
    "rozgar": "employment job", "padhai": "education student", "chhatravriti": "scholarship", "bima": "insurance",
    "ilaj": "health hospital", "budhapa": "old age pension", "vidhwa": "widow", "mahila": "women",
    "beti": "daughter girl", "karz": "loan", "dukaan": "shop business", "mazdoor": "worker labour",
}

_AADHAAR_RE = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{13,18}(?!\d)")


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------
def provider_config():
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if provider in {"none", "offline", "off"}:
        return {"provider": "offline"}
    if provider == "gemini" or (not provider and gemini_key):
        if gemini_key:
            return {"provider": "gemini", "key": gemini_key,
                    "model": os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()}
    if provider in {"openai", "openai_compatible"} or (not provider and openai_key):
        model = os.getenv("OPENAI_MODEL", "").strip()
        if openai_key and model:
            return {"provider": "openai", "key": openai_key, "model": model,
                    "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()}
    return {"provider": "offline"}


def provider_status():
    cfg = provider_config()
    return {"mode": cfg["provider"], "model": cfg.get("model")}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def redact(text: str):
    redacted = _AADHAAR_RE.sub("[redacted]", text)
    redacted = _LONG_NUMBER_RE.sub("[redacted]", redacted)
    return redacted, redacted != text


def _abbreviations(name: str):
    found = set(re.findall(r"\(([^)]+)\)", name))
    out = set()
    for item in found:
        cleaned = item.lower().replace("formerly", "").strip()
        if cleaned:
            out.add(cleaned)
            out.add(cleaned.replace("-", "").replace(" ", ""))
    return out


def expand_query(query: str) -> str:
    """Append English search terms for Hindi/Hinglish keywords so TF-IDF can match them."""
    q = query.lower()
    extra = [terms for word, terms in QUERY_EXPANSIONS.items()
             if (word in q if not word.isascii() else re.search(rf"\b{re.escape(word)}\b", q))]
    return f"{query} {' '.join(extra)}".strip()


def _name_hits(query: str, scheme) -> int:
    """Strong signal: the user named the scheme or its abbreviation (PM-KISAN, PMAY-G, Ujjwala...)."""
    q = query.lower()
    q_compact = re.sub(r"[\s\-]", "", q)
    hits = 0
    for abbr in _abbreviations(scheme["name"]):
        if len(abbr) >= 3 and (re.search(rf"\b{re.escape(abbr)}\b", q) or (len(abbr) >= 5 and abbr in q_compact)):
            hits += 1
    base = scheme["name"].split("(")[0].strip().lower()
    distinctive = [w for w in re.findall(r"[a-z]+", base)
                   if len(w) >= 5 and w not in {"pradhan", "mantri", "yojana", "scheme", "national", "mukhyamantri",
                                                "programme", "central", "sector", "students", "india", "bharat"}]
    if len(base) > 6 and base in q:
        hits += 2
    elif any(re.search(rf"\b{w}\b", q) for w in distinctive):
        hits += 1
    return hits


def _tag_hits(query: str, scheme) -> int:
    q = query.lower()
    return sum(1 for tag in scheme.get("tags") or []
               if len(tag) >= 3 and re.search(rf"(?<!\w){re.escape(tag.lower())}(?!\w)", q))


def retrieve(query: str, schemes: list, k: int = TOP_K):
    if not schemes or not query.strip():
        return []
    expanded = expand_query(query)
    ranked = rank_schemes(expanded, schemes)
    for s in ranked:
        s["_hits"] = _name_hits(query, s)
        s["_score"] = s["relevance_score"] + 0.6 * s["_hits"] + 0.12 * _tag_hits(expanded, s)
    ranked.sort(key=lambda s: s["_score"], reverse=True)
    if not ranked or ranked[0]["_score"] <= 0.05:
        return []
    cutoff = max(0.05, 0.3 * ranked[0]["_score"])
    return [s for s in ranked if s["_score"] >= cutoff][:k]


def detect_intent(text: str):
    t = text.lower()
    return [name for name, words in _INTENTS.items() if any(w in t for w in words)]


def is_personal_query(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _PERSONAL_MATCH)


def _profile_summary(profile: dict) -> str:
    if not profile:
        return ""
    labels = []

    def add(label, value):
        if value is not None and value != "":
            labels.append(f"{label}: {value}")

    add("Age", profile.get("age"))
    add("Gender", profile.get("gender"))
    add("State", profile.get("state"))
    add("Area", AREAS.get(profile.get("area") or "", profile.get("area")))
    occ = profile.get("occupation")
    if occ:
        from .engine import normalize_occupation
        add("Occupation", OCCUPATIONS.get(normalize_occupation(occ), occ))
    if profile.get("annual_income") is not None:
        add("Annual family income", format_inr(profile["annual_income"]))
    add("Social category", profile.get("social_category"))
    add("Marital status", MARITAL_STATUSES.get(profile.get("marital_status") or "", profile.get("marital_status")))
    add("Studying", STUDENT_LEVELS.get(profile.get("student_level") or "", profile.get("student_level")))
    for key, label in (("disability_status", "Person with disability"), ("bpl_card", "BPL/AAY/PHH ration card"),
                       ("income_tax_payer", "Income-tax payer"), ("owns_agri_land", "Owns farm land"),
                       ("owns_pucca_house", "Owns pucca house"), ("has_bank_account", "Has bank account")):
        if isinstance(profile.get(key), bool):
            add(label, "Yes" if profile[key] else "No")
    return "; ".join(labels)


def _scheme_block(index: int, s: dict, profile: dict | None) -> str:
    lines = [f"[S{index}] {s['name']} — {s.get('category')} · {s.get('level', 'Central')}"
             + (f" ({', '.join(s.get('states') or [])})" if s.get("states") else "")]
    if s.get("ministry"):
        lines.append(f"Ministry/Department: {s['ministry']}")
    lines.append(f"About: {s.get('description')}")
    if s.get("benefits"):
        lines.append(f"Benefits: {s['benefits']}")
    if s.get("eligibility_criteria"):
        lines.append("Recorded eligibility rules: " + "; ".join(s["eligibility_criteria"]))
    if s.get("additional_conditions"):
        lines.append("Other conditions: " + "; ".join(s["additional_conditions"]))
    if s.get("documents"):
        lines.append("Documents: " + ", ".join(s["documents"]))
    if s.get("how_to_apply"):
        lines.append(f"How to apply: {s['how_to_apply']}")
    lines.append(f"Official link: {s.get('official_url')}")
    if s.get("source_verified_at"):
        lines.append(f"Information last verified: {s['source_verified_at']}")
    if profile:
        outcome = s.get("eligibility") or evaluate(profile, s.get("rules") or {})
        status = {"eligible_by_recorded_rules": "meets all recorded rules",
                  "ineligible": "does NOT meet: " + "; ".join(
                      c["label"] for c in outcome["checks"] if c["result"] == "fail"),
                  "insufficient_information": "needs more details: " + (", ".join(
                      f.replace("_", " ") for f in outcome["missing_fields"]) or "check official portal")}
        lines.append(f"Preliminary screening for this user: {status[outcome['status']]}")
    return "\n".join(lines)


def build_context(schemes: list, profile: dict | None) -> str:
    parts = []
    summary = _profile_summary(profile or {})
    if summary:
        parts.append("USER PROFILE (self-reported): " + summary)
    if schemes:
        parts.append("SCHEME CONTEXT:\n" + "\n\n".join(_scheme_block(i + 1, s, profile) for i, s in enumerate(schemes)))
    else:
        parts.append("SCHEME CONTEXT: (no matching scheme found in the JanSetu database)")
    return "\n\n".join(parts)


def _clean_history(history):
    items = []
    for msg in (history or [])[-MAX_HISTORY:]:
        if not isinstance(msg, dict):
            continue
        role = "assistant" if msg.get("role") in {"assistant", "model", "bot"} else "user"
        content = str(msg.get("content") or "").strip()[:MAX_MESSAGE_CHARS]
        if not content:
            continue
        if role == "user":
            content = redact(content)[0]
        if items and items[-1]["role"] == role:
            items[-1]["content"] += "\n" + content
        else:
            items.append({"role": role, "content": content})
    while items and items[0]["role"] != "user":
        items.pop(0)
    return items


# ---------------------------------------------------------------------------
# LLM providers (plain HTTPS, no SDK dependency)
# ---------------------------------------------------------------------------
def _post_json(url, payload, headers, timeout=25):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers},
                                     method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _call_gemini(cfg, system, messages):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages]
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }
    data = _post_json(url, payload, {"x-goog-api-key": cfg["key"]})
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {data.get('promptFeedback')}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise RuntimeError(f"Gemini returned empty text (finishReason={candidates[0].get('finishReason')})")
    return text


def _call_openai(cfg, system, messages):
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    payload = {"model": cfg["model"], "temperature": 0.3, "max_tokens": 900,
               "messages": [{"role": "system", "content": system}] + messages}
    data = _post_json(url, payload, {"Authorization": f"Bearer {cfg['key']}"})
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if not text.strip():
        raise RuntimeError("Empty completion")
    return text.strip()


# ---------------------------------------------------------------------------
# Offline (deterministic) answers
# ---------------------------------------------------------------------------
def _bullets(items, limit=6):
    return "\n".join(f"- {i}" for i in items[:limit])


def offline_answer(message: str, schemes: list, profile: dict | None, personal: bool) -> str:
    text = message.strip().lower()
    if text.strip("!.? ") in _GREETINGS:
        return ("Namaste! I'm **JanSetu Sahayak**. I can help you:\n"
                "- find government schemes for farmers, students, women, workers and senior citizens\n"
                "- explain benefits, documents and how to apply\n"
                "- check which schemes you may be eligible for (try the **Check Eligibility** tab)\n\n"
                "Ask me something like *\"What documents are needed for PM-KISAN?\"*")
    if not schemes:
        return ("I can help with government schemes and public services, but I couldn't find a matching scheme "
                "in JanSetu's verified database for that. Try words like *scholarship*, *pension*, *farmer*, "
                "*housing* or *loan*, or browse all schemes on https://www.myscheme.gov.in.")
    intents = detect_intent(text)
    if personal and profile:
        eligible = [s for s in schemes if (s.get("eligibility") or {}).get("status") == "eligible_by_recorded_rules"]
        if eligible:
            lines = [f"**{s['name']}** — {s.get('benefits') or s['description']}" for s in eligible[:5]]
            return ("Based on the details you shared, you **may be eligible** for:\n" + _bullets(lines) +
                    "\n\nOpen **Check Eligibility** for a rule-by-rule explanation, and confirm on the official "
                    "portal before applying.")
    top = schemes[0]
    wants_list = any(w in text for w in _LIST_WORDS)
    second = schemes[1].get("_score", 0) if len(schemes) > 1 else 0
    clear_winner = top.get("_score", 0) >= 1.8 * second and top.get("relevance_score", 0) >= 0.2
    focused = len(schemes) == 1 or (top.get("_hits", 0) > 0 and not wants_list) or (clear_winner and not wants_list)
    if focused:
        s = top
        out = [f"**{s['name']}**", s.get("description", "")]
        if not intents or "benefits" in intents:
            if s.get("benefits"):
                out.append(f"**Benefits:** {s['benefits']}")
        if not intents or "eligibility" in intents:
            crit = (s.get("eligibility_criteria") or []) + (s.get("additional_conditions") or [])
            if crit:
                out.append("**Who can apply:**\n" + _bullets(crit, 7))
        if "documents" in intents and s.get("documents"):
            out.append("**Documents usually needed:**\n" + _bullets(s["documents"], 8))
        if ("apply" in intents or not intents) and s.get("how_to_apply"):
            out.append(f"**How to apply:** {s['how_to_apply']}")
        if profile:
            outcome = s.get("eligibility") or evaluate(profile, s.get("rules") or {})
            verdict = {"eligible_by_recorded_rules": "✅ You meet all the recorded rules (preliminary).",
                       "ineligible": "❌ Based on your details, you don't meet: " + "; ".join(
                           c["label"] for c in outcome["checks"] if c["result"] == "fail") + ".",
                       "insufficient_information": "ℹ️ I need a few more details to check your eligibility."}
            out.append(verdict[outcome["status"]])
        out.append(f"Official link: {s['official_url']}")
        return "\n\n".join(p for p in out if p)
    lines = [f"**{s['name']}** — {s.get('benefits') or s['description']}" for s in schemes[:4]]
    return ("Here are schemes related to your question:\n" + _bullets(lines) +
            "\n\nAsk me about any one of them for eligibility, documents or how to apply.")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def answer(message: str, history: list, all_schemes: list, profile: dict | None = None):
    message = (message or "").strip()[:MAX_MESSAGE_CHARS]
    clean_message, redacted = redact(message)
    history = _clean_history(history)
    personal = bool(profile) and is_personal_query(clean_message)

    if personal:
        screened = screen_all(profile, all_schemes)["results"]
        sources = [s for s in screened if s["eligibility"]["status"] == "eligible_by_recorded_rules"][:6]
        if len(sources) < 3:
            sources += [s for s in screened if s["eligibility"]["status"] == "insufficient_information"][:3]
    else:
        previous_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        sources = retrieve(clean_message, all_schemes)
        if not sources or (sources[0].get("_hits", 0) == 0 and sources[0]["relevance_score"] < 0.15):
            # follow-up questions ("what documents for it?") — fall back to the previous turn's topic
            combined = retrieve(f"{previous_user} {clean_message}", all_schemes) if previous_user else []
            sources = combined or sources
        if profile:
            for s in sources:
                s["eligibility"] = evaluate(profile, s.get("rules") or {})

    cfg = provider_config()
    mode = cfg["provider"]
    reply, error = None, None
    if mode != "offline":
        system = SYSTEM_PROMPT + "\n\n" + build_context(sources, profile)
        messages = history + [{"role": "user", "content": clean_message}]
        try:
            reply = _call_gemini(cfg, system, messages) if mode == "gemini" else _call_openai(cfg, system, messages)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, ValueError, KeyError) as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300] if isinstance(exc, urllib.error.HTTPError) else str(exc)
            log.warning("LLM call failed (%s): %s", mode, detail)
            error = "The AI service is unavailable right now, so this answer comes from JanSetu's scheme database."
            mode = "offline"
    if reply is None:
        reply = offline_answer(clean_message, sources, profile, personal)

    return {
        "reply": reply,
        "mode": mode,
        "notice": error,
        "redacted": redacted,
        "sources": [{"id": s.get("id"), "name": s["name"], "category": s.get("category"),
                     "official_url": s.get("official_url"),
                     "status": (s.get("eligibility") or {}).get("status")} for s in sources[:5]],
    }
