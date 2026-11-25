"""Deterministic, explainable eligibility rules + TF-IDF relevance ranking.

Design principles (unchanged from v0.1):
  * No fabricated eligibility. A rule we cannot evaluate is reported as "unknown",
    never as a pass. Unsupported rule keys fail closed.
  * Every outcome carries a human-readable explanation so citizens can see *why*.
  * The relevance score is not a probability of approval.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Controlled vocabularies (also served to the frontend through /api/meta)
# ---------------------------------------------------------------------------
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

OCCUPATIONS = {
    "farmer": "Farmer / Cultivator",
    "agricultural_labourer": "Agricultural labourer",
    "fisher": "Fisher / Fish farmer",
    "street_vendor": "Street vendor / Hawker",
    "artisan": "Artisan / Craftsperson",
    "daily_wage_worker": "Construction / Daily-wage worker",
    "domestic_worker": "Domestic worker",
    "gig_worker": "Gig / Platform worker",
    "self_employed": "Small business / Self-employed",
    "salaried_private": "Salaried (private sector)",
    "government_employee": "Government employee",
    "student": "Student",
    "unemployed": "Unemployed / Job seeker",
    "homemaker": "Homemaker",
    "retired": "Retired",
    "other": "Other",
}

# Ordered keyword → occupation key mapping used to normalise free-text values
# entered before occupations became a dropdown.
_OCCUPATION_SYNONYMS = [
    (("agricultural lab", "farm lab", "khet mazdoor", "kheti mazdoor"), "agricultural_labourer"),
    (("farmer", "kisan", "cultivat", "agricultur", "kheti", "किसान"), "farmer"),
    (("fisher", "fish", "machhuar"), "fisher"),
    (("vendor", "hawker", "rehri", "thela", "pheri"), "street_vendor"),
    (("artisan", "craft", "carpenter", "blacksmith", "potter", "weaver", "tailor", "cobbler",
      "goldsmith", "mason", "barber", "lohar", "kumhar", "darzi"), "artisan"),
    (("construction", "daily wage", "labour", "labor", "mazdoor", "worker"), "daily_wage_worker"),
    (("domestic", "maid", "house help"), "domestic_worker"),
    (("gig", "delivery", "platform", "driver"), "gig_worker"),
    (("government", "govt", "sarkari", "psu"), "government_employee"),
    (("business", "shop", "self employ", "self-employ", "entrepreneur", "trader"), "self_employed"),
    (("engineer", "salaried", "private job", "employee", "developer", "it ", "software"), "salaried_private"),
    (("student", "studying", "scholar"), "student"),
    (("unemploy", "job seeker", "jobless", "berozgar"), "unemployed"),
    (("homemaker", "housewife", "home maker", "grihini"), "homemaker"),
    (("retired", "pensioner"), "retired"),
]

GENDERS = ["Woman", "Man", "Transgender", "Non-binary", "Prefer not to say"]
SOCIAL_CATEGORIES = ["General", "EWS", "OBC", "SC", "ST", "Prefer not to say"]
AREAS = {"rural": "Rural (village)", "urban": "Urban (town / city)"}
MARITAL_STATUSES = {
    "unmarried": "Unmarried",
    "married": "Married",
    "widowed": "Widowed",
    "divorced": "Divorced / Separated / Abandoned",
}
STUDENT_LEVELS = {
    "none": "Not currently studying",
    "class_1_5": "Class 1 - 5",
    "class_6_8": "Class 6 - 8",
    "class_9_10": "Class 9 - 10",
    "class_11_12": "Class 11 - 12",
    "iti_diploma": "ITI / Diploma / Polytechnic",
    "undergraduate": "Undergraduate (UG)",
    "postgraduate": "Postgraduate (PG)",
    "phd": "PhD / Research",
}
EDUCATION_LEVELS = ["No formal education", "Primary", "Secondary", "Higher secondary", "Diploma",
                    "Graduate", "Postgraduate"]
EMPLOYMENT_STATUSES = ["Employed", "Self-employed", "Unemployed", "Student", "Retired", "Homemaker"]

# Questions shown to citizens for each profile field (used for "answer N more questions").
FIELD_QUESTIONS = {
    "age": "What is your age?",
    "state": "Which state do you live in?",
    "annual_income": "What is your annual family income?",
    "occupation": "What is your main occupation?",
    "gender": "What is your gender?",
    "social_category": "What is your social category?",
    "area": "Do you live in a rural or urban area?",
    "marital_status": "What is your marital status?",
    "student_level": "Are you currently studying? At what level?",
    "disability_status": "Do you have a disability (with certificate)?",
    "income_tax_payer": "Have you (or your family) paid income tax?",
    "organised_sector_member": "Are you a member of EPFO, ESIC or NPS?",
    "govt_employee_in_family": "Is anyone in your family a government employee?",
    "has_bank_account": "Do you have a savings bank / post office account?",
    "bpl_card": "Do you hold a BPL / Antyodaya / priority household ration card?",
    "owns_agri_land": "Does your family own agricultural land?",
    "land_hectares": "How much agricultural land (in hectares)?",
    "owns_pucca_house": "Does your family own a pucca (permanent) house?",
    "has_lpg_connection": "Does your household already have an LPG connection?",
    "pregnant_or_lactating": "Are you pregnant or a lactating mother?",
    "daughter_below_10": "Do you have a daughter below 10 years of age?",
}

# ---------------------------------------------------------------------------
# Rule specification: rule key -> (profile field, comparison)
# ---------------------------------------------------------------------------
RULES = {
    "age_min": ("age", "gte"),
    "age_max": ("age", "lte"),
    "income_max": ("annual_income", "lte"),
    "income_min": ("annual_income", "gte"),
    "states": ("state", "in"),
    "occupations": ("occupation", "in"),
    "occupations_not": ("occupation", "not_in"),
    "genders": ("gender", "in"),
    "social_categories": ("social_category", "in"),
    "areas": ("area", "in"),
    "marital_statuses": ("marital_status", "in"),
    "student_levels": ("student_level", "in"),
    "disability": ("disability_status", "eq"),
    "income_tax_payer": ("income_tax_payer", "eq"),
    "organised_sector_member": ("organised_sector_member", "eq"),
    "govt_employee_in_family": ("govt_employee_in_family", "eq"),
    "bank_account": ("has_bank_account", "eq"),
    "bpl": ("bpl_card", "eq"),
    "land_owner": ("owns_agri_land", "eq"),
    "land_max_hectares": ("land_hectares", "lte"),
    "pucca_house": ("owns_pucca_house", "eq"),
    "lpg_connection": ("has_lpg_connection", "eq"),
    "pregnant_or_lactating": ("pregnant_or_lactating", "eq"),
    "daughter_below_10": ("daughter_below_10", "eq"),
}
SUPPORTED = set(RULES) | {"any_of"}

_BOOL_TEXT = {
    "disability": ("Person with disability (certificate required)", "Not for persons with disability"),
    "income_tax_payer": ("Income-tax payer", "Not an income-tax payer"),
    "organised_sector_member": ("Member of EPFO / ESIC / NPS", "Not a member of EPFO, ESIC or NPS"),
    "govt_employee_in_family": ("Government employee in family", "No family member in government service"),
    "bank_account": ("Has a savings bank / post office account", "No bank account"),
    "bpl": ("Holds a BPL / Antyodaya / priority household ration card", "Not BPL"),
    "land_owner": ("Family owns agricultural land", "Does not own agricultural land"),
    "pucca_house": ("Family owns a pucca house", "Family does not own a pucca house"),
    "lpg_connection": ("Household has an LPG connection", "No LPG connection in the household"),
    "pregnant_or_lactating": ("Pregnant or lactating mother", "Not pregnant / lactating"),
    "daughter_below_10": ("Has a daughter below 10 years", "No daughter below 10"),
}

DISCLAIMER = ("Preliminary rule-based screening only; verify current requirements with the "
              "official authority before applying.")


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
def format_inr(value) -> str:
    """Format a number with Indian digit grouping: 250000 -> ₹2,50,000."""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return str(value)
    sign = "-" if number < 0 else ""
    digits = str(abs(number))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        digits = f"{head},{tail}"
    return f"{sign}₹{digits}"


def normalize_occupation(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in OCCUPATIONS:
        return text
    for label_key, label in OCCUPATIONS.items():
        if text == label.lower():
            return label_key
    padded = f" {text} "
    for keywords, key in _OCCUPATION_SYNONYMS:
        if any(k in padded for k in keywords):
            return key
    return "other"


def normalize_gender(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"woman", "female", "f", "girl", "mahila", "महिला"}:
        return "female"
    if text in {"man", "male", "m", "boy", "purush", "पुरुष"}:
        return "male"
    if text.startswith("trans"):
        return "transgender"
    if text in {"non-binary", "nonbinary", "non binary"}:
        return "non_binary"
    return None  # "Prefer not to say" and unknown values stay unknown


def normalize_category(value):
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text.startswith("PREFER"):
        return None
    return {"GENERAL": "GENERAL", "GEN": "GENERAL"}.get(text, text)


def _normalize_key(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


_NORMALIZERS = {
    "occupation": normalize_occupation,
    "gender": normalize_gender,
    "social_category": normalize_category,
    "state": lambda v: _normalize_key(v),
    "area": _normalize_key,
    "marital_status": _normalize_key,
    "student_level": _normalize_key,
}


def _normalize_expected(field, values):
    norm = _NORMALIZERS.get(field, _normalize_key)
    out = set()
    for item in values:
        if field == "gender":
            # rule values are canonical keys such as "female"
            out.add(str(item).strip().lower())
        else:
            normalized = norm(item)
            if normalized is not None:
                out.add(normalized)
    return out


def _display(field, value):
    if value is None:
        return "not provided"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if field == "annual_income":
        return format_inr(value)
    if field == "occupation":
        key = normalize_occupation(value)
        return OCCUPATIONS.get(key, str(value))
    if field == "area":
        return AREAS.get(str(value), str(value))
    if field == "marital_status":
        return MARITAL_STATUSES.get(str(value), str(value))
    if field == "student_level":
        return STUDENT_LEVELS.get(str(value), str(value))
    if field == "land_hectares":
        return f"{value} ha"
    return str(value)


def _join(items, word="or"):
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


def describe_rule(key, expected) -> str:
    """Human-readable description of one recorded rule."""
    if key == "any_of":
        parts = []
        for group in expected or []:
            inner = [describe_rule(k, v) for k, v in group.items()]
            parts.append(" and ".join(inner))
        return "Any one of: " + " | ".join(parts)
    if key == "age_min":
        return f"Age {expected} years or above"
    if key == "age_max":
        return f"Age {expected} years or below"
    if key == "income_max":
        return f"Annual family income up to {format_inr(expected)}"
    if key == "income_min":
        return f"Annual family income at least {format_inr(expected)}"
    if key == "land_max_hectares":
        return f"Landholding up to {expected} hectares"
    if key == "states":
        return "Resident of " + _join(expected)
    if key == "occupations":
        return "Occupation: " + _join(OCCUPATIONS.get(o, o) for o in expected)
    if key == "occupations_not":
        return "Not applicable to: " + _join((OCCUPATIONS.get(o, o) for o in expected), "and")
    if key == "genders":
        labels = {"female": "Women", "male": "Men", "transgender": "Transgender persons"}
        return _join(labels.get(g, g) for g in expected) + " only"
    if key == "social_categories":
        return "/".join(expected) + " category"
    if key == "areas":
        return "Lives in a " + _join(AREAS.get(a, a).split(" (")[0].lower() for a in expected) + " area"
    if key == "marital_statuses":
        return "Marital status: " + _join(MARITAL_STATUSES.get(m, m) for m in expected)
    if key == "student_levels":
        return "Currently studying in: " + _join(STUDENT_LEVELS.get(s, s) for s in expected)
    if key in _BOOL_TEXT:
        yes, no = _BOOL_TEXT[key]
        return yes if expected else no
    return key.replace("_", " ")


def describe_rules(rules) -> list[str]:
    return [describe_rule(k, v) for k, v in (rules or {}).items()]


def validate_rules(rules, path="rules"):
    """Raise ValueError if a rule set contains unknown keys or malformed values."""
    if not isinstance(rules, dict):
        raise ValueError(f"{path} must be an object")
    for key, value in rules.items():
        if key not in SUPPORTED:
            raise ValueError(f"{path}: unsupported eligibility rule '{key}'")
        if key == "any_of":
            if not isinstance(value, list) or not value:
                raise ValueError(f"{path}.any_of must be a non-empty list")
            for i, group in enumerate(value):
                if not isinstance(group, dict) or not group or "any_of" in group:
                    raise ValueError(f"{path}.any_of[{i}] must be a non-empty rule object")
                validate_rules(group, f"{path}.any_of[{i}]")
            continue
        field, op = RULES[key]
        if op in {"in", "not_in"}:
            if not isinstance(value, list) or not value:
                raise ValueError(f"{path}.{key} must be a non-empty list")
        elif op == "eq":
            if not isinstance(value, bool):
                raise ValueError(f"{path}.{key} must be true or false")
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path}.{key} must be a number")
        if key in {"occupations", "occupations_not"}:
            unknown = [o for o in value if o not in OCCUPATIONS]
            if unknown:
                raise ValueError(f"{path}.{key}: unknown occupations {unknown}")
        if key == "student_levels":
            unknown = [s for s in value if s not in STUDENT_LEVELS]
            if unknown:
                raise ValueError(f"{path}.{key}: unknown student levels {unknown}")


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def _evaluate_rule(profile, key, expected):
    if key not in SUPPORTED:
        return {"field": key, "result": "unknown", "label": key.replace("_", " "),
                "reason": "Unsupported rule; manual verification required"}
    if key == "any_of":
        return _evaluate_any_of(profile, expected)

    field, op = RULES[key]
    label = describe_rule(key, expected)
    actual = profile.get(field)
    if actual is None or actual == "":
        return {"field": key, "profile_field": field, "result": "unknown", "label": label,
                "reason": f"Missing {field.replace('_', ' ')}", "missing": [field]}
    try:
        if op in {"in", "not_in"}:
            norm = _NORMALIZERS.get(field, _normalize_key)
            actual_norm = norm(actual)
            if actual_norm is None:
                return {"field": key, "profile_field": field, "result": "unknown", "label": label,
                        "reason": f"{field.replace('_', ' ').capitalize()} not specified",
                        "missing": [field]}
            allowed = _normalize_expected(field, expected)
            ok = actual_norm in allowed if op == "in" else actual_norm not in allowed
        elif op == "eq":
            if not isinstance(actual, bool):
                raise ValueError("expected a yes/no answer")
            ok = actual is expected
        else:
            number = float(actual)
            ok = number >= float(expected) if op == "gte" else number <= float(expected)
    except (TypeError, ValueError):
        return {"field": key, "profile_field": field, "result": "unknown", "label": label,
                "reason": "Invalid profile or rule value", "missing": [field]}
    return {"field": key, "profile_field": field, "result": "pass" if ok else "fail",
            "label": label, "actual": actual, "actual_display": _display(field, actual),
            "expected": expected}


def _evaluate_any_of(profile, groups):
    label = describe_rule("any_of", groups)
    group_results, missing = [], []
    for group in groups or []:
        checks = [_evaluate_rule(profile, k, v) for k, v in group.items()]
        results = {c["result"] for c in checks}
        if "fail" in results:
            group_results.append("fail")
        elif "unknown" in results:
            group_results.append("unknown")
            for c in checks:
                missing.extend(c.get("missing", []))
        else:
            group_results.append("pass")
    if "pass" in group_results:
        result = "pass"
    elif group_results and all(r == "fail" for r in group_results):
        result = "fail"
    else:
        result = "unknown"
    check = {"field": "any_of", "result": result, "label": label}
    if result == "unknown":
        check["reason"] = "Need more details to check these alternatives"
        check["missing"] = sorted(set(missing))
    return check


def evaluate(profile, rules):
    profile = profile or {}
    checks = [_evaluate_rule(profile, key, expected) for key, expected in (rules or {}).items()]
    statuses = {c["result"] for c in checks}
    if "fail" in statuses:
        status = "ineligible"
    elif "unknown" in statuses or not checks:
        status = "insufficient_information"
    else:
        status = "eligible_by_recorded_rules"
    passed = sum(c["result"] == "pass" for c in checks)
    missing = sorted({m for c in checks for m in c.get("missing", [])})
    return {
        "status": status,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "score": round(passed / len(checks), 3) if checks else 0.0,
        "missing_fields": missing,
        "disclaimer": DISCLAIMER,
    }


_STATUS_ORDER = {"eligible_by_recorded_rules": 0, "insufficient_information": 1, "ineligible": 2}


def screen_all(profile, schemes):
    """Evaluate every scheme for one profile; returns sorted results + adaptive questions."""
    results = []
    for scheme in schemes:
        outcome = evaluate(profile, scheme.get("rules") or {})
        results.append({**scheme, "eligibility": outcome})
    # Within a status group, schemes that check more of the person's details first (more targeted matches).
    results.sort(key=lambda s: (_STATUS_ORDER[s["eligibility"]["status"]],
                                -s["eligibility"]["score"], -s["eligibility"]["passed"], s["name"]))
    summary = {
        "eligible": sum(r["eligibility"]["status"] == "eligible_by_recorded_rules" for r in results),
        "needs_information": sum(r["eligibility"]["status"] == "insufficient_information" for r in results),
        "ineligible": sum(r["eligibility"]["status"] == "ineligible" for r in results),
        "total": len(results),
    }
    # Adaptive questioning: which unanswered fields would let us evaluate the most schemes?
    counts = {}
    for r in results:
        if r["eligibility"]["status"] != "insufficient_information":
            continue
        for field in r["eligibility"]["missing_fields"]:
            counts[field] = counts.get(field, 0) + 1
    suggested = [{"field": f, "question": FIELD_QUESTIONS.get(f, f.replace("_", " ")), "schemes_affected": n}
                 for f, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"results": results, "summary": summary, "suggested_questions": suggested[:6],
            "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Relevance ranking
# ---------------------------------------------------------------------------
def scheme_text(s) -> str:
    parts = [s.get("name", ""), s.get("description", ""), s.get("category", ""), s.get("benefits") or "",
             " ".join(s.get("tags") or []), " ".join(describe_rules(s.get("rules"))),
             " ".join(s.get("additional_conditions") or [])]
    return " ".join(p for p in parts if p)


_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_text(text: str) -> str:
    """Lower-case and apply a crude plural stemmer (widows -> widow, farmers -> farmer)."""
    words = []
    for w in _WORD_RE.findall((text or "").lower()):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
            w = w[:-1]
        words.append(w)
    return " ".join(words)


def rank_schemes(query, schemes):
    """Actual unsupervised ML baseline: TF-IDF with cosine similarity."""
    if not schemes:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    corpus = [normalize_text(scheme_text(s)) for s in schemes]
    query = normalize_text(query)
    if not query.strip():
        return [{**s, "relevance_score": 0.0} for s in schemes]
    try:
        vectors = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True) \
            .fit_transform([query] + corpus)
        scores = cosine_similarity(vectors[0:1], vectors[1:]).ravel()
    except ValueError:
        scores = [0.0] * len(schemes)
    return sorted([{**s, "relevance_score": round(float(score), 4)} for s, score in zip(schemes, scores)],
                  key=lambda x: x["relevance_score"], reverse=True)
