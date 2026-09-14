"""Explainable, profile-driven job fit and remote eligibility assessment."""

import re
from datetime import datetime, timezone
from typing import Optional



def _profile_or_active(profile: dict = None) -> dict:
    if profile is not None:
        return profile
    from core.profile import get_active_profile
    return get_active_profile()


def extract_tech_stack(text: str, profile: dict = None) -> list[str]:
    profile = _profile_or_active(profile)
    terms = profile["search"].get("relevant_tech") or []
    lowered = text.lower()
    return [term for term in terms if re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", lowered)]


def estimate_experience_level(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("intern", "internship", "trainee", "entry-level", "entry level", "new grad", "fresher")):
        return "fresher"
    if any(word in lowered for word in ("director", "head of", "principal", "staff", "lead", "senior manager", "10+ years", "8+ years")):
        return "senior"
    if any(word in lowered for word in ("junior", "jr.", "1-2 years", "1+ year")):
        return "junior"
    return "mid"


def extract_experience_requirement(text: str) -> dict:
    """Extract explicit year requirements without treating a senior title as years."""
    lowered = text.lower().replace("–", "-").replace("—", "-")
    ranges = re.findall(r"\b(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*(?:\+\s*)?years?", lowered)
    pluses = re.findall(r"\b(\d{1,2})\s*\+\s*years?", lowered)
    minimums = re.findall(r"(?:minimum|min\.?|at least)\s+(?:of\s+)?(\d{1,2})\s*years?", lowered)
    if ranges:
        low, high = map(int, ranges[0])
        return {"minimum": low, "maximum": high, "text": f"{low}-{high} years", "hard_minimum": False}
    values = [int(v) for v in minimums or pluses]
    if values:
        years = max(values)
        return {"minimum": years, "maximum": None, "text": f"{years}+ years", "hard_minimum": years >= 10}
    return {"minimum": None, "maximum": None, "text": "Not stated", "hard_minimum": False}


def assess_experience(text: str, candidate_years: int = 8) -> dict:
    requirement = extract_experience_requirement(text)
    minimum, maximum = requirement["minimum"], requirement["maximum"]
    lowered = text.lower()
    equivalence = any(p in lowered for p in ("equivalent experience", "relevant experience", "or equivalent", "comparable experience"))
    if minimum is None:
        compatibility, points = "Needs Verification", 6
    elif maximum is not None and minimum <= candidate_years <= maximum:
        compatibility, points = "Strong Match", 15
    elif 6 <= minimum <= 9:
        compatibility, points = "Strong Match", 15
    elif minimum >= 10 and equivalence:
        compatibility, points = "Potential Match — equivalent experience allowed", 8
    elif minimum >= 10:
        compatibility, points = "Gap — hard 10+ year requirement", 0
    elif minimum <= candidate_years:
        compatibility, points = "Compatible", 10
    else:
        compatibility, points = "Gap", 0
    return {**requirement, "compatibility": compatibility, "points": points, "equivalent_allowed": equivalence}


def check_india_friendly(location: str, description: str, profile: dict = None) -> dict:
    """Hard-gate remote-from-India eligibility with confidence and evidence."""
    profile = _profile_or_active(profile)
    cfg = profile.get("location", {})
    loc = (location or "").lower()
    full = f"{location or ''} {description or ''}".lower()
    reject = cfg.get("india_negative") or []
    explicit_reject = [term for term in reject if term.lower() in full]
    onsite = re.search(r"\b(on[ -]?site|hybrid)\b", loc) or re.search(r"must (?:work|be) (?:in|from) (?:the )?office", full)
    if onsite:
        return {"result": "no", "eligibility": "Ineligible", "confidence": "High", "note": "On-site or hybrid role"}
    if explicit_reject:
        return {"result": "no", "eligibility": "Ineligible", "confidence": "High", "note": f"Country restriction: {', '.join(explicit_reject[:3])}"}

    india = re.search(r"(?:remote\s*[-/]?\s*india|india\s*[-/]?\s*remote|remote[^.]{0,35}(?:from|in|based in) india|india[^.]{0,35}(?:employee|contractor))", full)
    if india:
        return {"result": "yes", "eligibility": "Eligible", "confidence": "High", "note": "Remote work from India explicitly allowed"}

    global_remote = re.search(r"(?:worldwide|globally?|anywhere|all countries)[^.]{0,50}remote|remote[^.]{0,50}(?:worldwide|globally?|anywhere|all countries)", full)
    apac_remote = re.search(r"(?:apac|asia(?: pacific)?)[^.]{0,40}remote|remote[^.]{0,40}(?:apac|asia(?: pacific)?)", full)
    if global_remote or apac_remote:
        excluded = re.search(r"(?:except|excluding|not available in)[^.]{0,60}india", full)
        if not excluded:
            signal = "Global/worldwide remote" if global_remote else "APAC/Asia remote"
            return {"result": "yes", "eligibility": "Eligible", "confidence": "Medium", "note": f"{signal}; India not excluded"}

    if "remote" in full:
        return {"result": "maybe", "eligibility": "Needs Verification", "confidence": "Low", "note": "Remote role, but India eligibility is not explicit"}
    return {"result": "no", "eligibility": "Ineligible", "confidence": "High", "note": "Role is not identified as remote"}


def _posted_age(posted_date: Optional[str], now: Optional[datetime] = None) -> dict:
    if not posted_date:
        return {"days": None, "label": "Unknown", "gap": "Posting date unavailable"}
    try:
        parsed = datetime.fromisoformat(str(posted_date).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        days = max(0, (current - parsed.astimezone(timezone.utc)).days)
        if days <= 7:
            return {"days": days, "label": f"{days} days old", "gap": ""}
        if days <= 30:
            return {"days": days, "label": f"{days} days old", "gap": "Older than the preferred 7-day window"}
        return {"days": days, "label": f"{days} days old", "gap": "Older than 30 days; verify it was reposted"}
    except (TypeError, ValueError):
        return {"days": None, "label": "Unknown", "gap": "Posting date could not be parsed"}


def classify_role_families(title: str, description: str, profile: dict) -> dict:
    """Classify function from responsibilities; use the title only as support.

    Multiple families can apply. Confidence is intentionally evidence-based and
    stays low when only the title provides a clue.
    """
    mapping = profile.get("scoring", {}).get("role_families") or {}
    description_lower = (description or "").lower()
    title_lower = (title or "").lower()
    matches = []
    for family, terms in mapping.items():
        description_hits = [term for term in terms if term.lower() in description_lower]
        title_hits = [term for term in terms if term.lower() in title_lower]
        if not description_hits and not title_hits:
            continue
        # Responsibility evidence dominates. A title-only result is retained for
        # review, but cannot receive high confidence or much fit credit.
        confidence = min(95, (35 + 15 * len(description_hits) + (5 if title_hits else 0)) if description_hits else 25)
        matches.append({
            "family": family,
            "confidence": confidence,
            "evidence": description_hits,
            "title_support": title_hits,
        })
    matches.sort(key=lambda item: (item["confidence"], len(item["evidence"])), reverse=True)
    if not matches:
        return {"primary": "Other / Needs Review", "secondary": [], "confidence": 0, "scores": {}, "evidence": []}
    primary = matches[0]
    return {
        "primary": primary["family"],
        "secondary": [item["family"] for item in matches[1:]],
        "confidence": primary["confidence"],
        "scores": {item["family"]: item["confidence"] for item in matches},
        "evidence": list(dict.fromkeys(hit for item in matches for hit in item["evidence"])),
    }


def score_job(title: str, description: str, location: str = "", profile: dict = None,
              posted_date: Optional[str] = None, now: Optional[datetime] = None) -> dict:
    profile = _profile_or_active(profile)
    search, scoring = profile["search"], profile["scoring"]
    title_lower = title.lower()
    description_lower = (description or "").lower()
    reasons, gaps = [], []

    excluded = [term for term in search.get("title_keywords_negative", []) if term.lower() in title_lower]
    positive = [term for term in search.get("title_keywords_positive", []) if term.lower() in title_lower]
    title_points = 5 if positive else 0
    if positive:
        reasons.append(f"Target title/role signals: {', '.join(positive[:5])}")
    # Negative titles are evaluated later against description-confirmed scope.

    strengths = scoring.get("strengths") or search.get("relevant_tech") or []
    matched = [term for term in strengths if term.lower() in description_lower]
    capability_points = min(25, len(matched) * 4)
    if matched:
        reasons.append(f"Relevant strengths: {', '.join(matched[:8])}")
    else:
        gaps.append("Few explicit matches to the candidate's AI, operations, or delivery strengths")

    leadership_terms = scoring.get("leadership_signals") or []
    leadership = [term for term in leadership_terms if term.lower() in description_lower]
    leadership_points = min(20, len(leadership) * 5)
    if leadership:
        reasons.append(f"Leadership scope: {', '.join(leadership[:5])}")

    exp = assess_experience(description_lower, int(scoring.get("candidate_years", 8)))
    responsibilities_strongly_align = len(matched) >= 5 and len(leadership) >= 2
    if exp["hard_minimum"] and not exp["equivalent_allowed"] and responsibilities_strongly_align:
        exp["compatibility"] = "Stretch Match — responsibilities strongly align"
        exp["points"] = 5
    if exp["points"] > 0:
        reasons.append(f"Experience: {exp['text']} — {exp['compatibility']}")
    elif "Gap" in exp["compatibility"]:
        gaps.append(f"Experience: {exp['text']} — {exp['compatibility']}")

    age = _posted_age(posted_date, now=now)
    if age["days"] is not None and age["days"] <= 7:
        reasons.append(f"Fresh posting: {age['label']}")
    if age["gap"]:
        gaps.append(age["gap"])

    families = classify_role_families(title, description, profile)
    role_family = families["primary"]
    seniority_matches = [
        label for label, terms in (scoring.get("seniority_titles") or {}).items()
        if any(term.lower() in title_lower for term in terms)
    ]
    seniority = seniority_matches[0] if seniority_matches else estimate_experience_level(description_lower).title()
    eligibility = check_india_friendly(location, description, profile)

    functional_points = min(25, len(families["evidence"]) * 5)
    outcome_terms = scoring.get("business_outcome_signals") or []
    outcomes = [term for term in outcome_terms if term.lower() in description_lower]
    outcome_points = min(10, len(outcomes) * 2)
    responsibility_points = functional_points + outcome_points
    if outcomes:
        reasons.append(f"Business outcomes: {', '.join(outcomes[:6])}")
    if families["evidence"]:
        reasons.append(f"Responsibility evidence: {', '.join(families['evidence'][:8])}")

    experience_points = exp["points"]
    score = max(0, min(100, responsibility_points + capability_points + leadership_points + experience_points + title_points))

    # A negative title is exclusionary only when the description also confirms
    # non-target IC work and contains no functional responsibility evidence.
    outside_terms = scoring.get("outside_scope_signals") or []
    outside_hits = [term for term in outside_terms if term.lower() in description_lower]
    confirmed_outside_scope = bool(excluded and outside_hits and not families["evidence"])
    if confirmed_outside_scope:
        gaps.append(f"Excluded title confirmed by responsibilities: {', '.join(excluded[:4])}")
        gaps.append(f"Description confirms outside-target scope: {', '.join(outside_hits[:5])}")
        score = min(score, 39)
    classification = "Excellent Fit" if score >= 85 else "Strong Fit" if score >= 70 else "Potential Fit" if score >= 55 else "Low Fit"
    resume_relevant_gaps = [
        gap for gap in gaps
        if not gap.startswith(("Older than", "Posting date"))
    ]
    resume_modify = bool(resume_relevant_gaps or role_family == "Other / Needs Review" or families["confidence"] < 60 or len(matched) < 4)

    return {
        "score": score,
        "fit_classification": classification,
        "tech_stack": extract_tech_stack(description_lower, profile),
        "experience_level": estimate_experience_level(description_lower),
        "experience_requirement": exp["text"],
        "experience_compatibility": exp["compatibility"],
        "seniority": seniority,
        "role_family": role_family,
        "secondary_role_families": families["secondary"],
        "role_family_confidence": families["confidence"],
        "role_family_scores": families["scores"],
        "responsibility_evidence": families["evidence"],
        "posted_age_days": age["days"],
        "posted_age": age["label"],
        "reasons": reasons,
        "red_flags": gaps,
        "important_gaps": gaps,
        "resume_modification_recommended": resume_modify,
        "india_friendly": eligibility["result"],
        "remote_india_eligibility": eligibility["eligibility"],
        "eligibility_confidence": eligibility["confidence"],
        "location_note": eligibility["note"],
    }
