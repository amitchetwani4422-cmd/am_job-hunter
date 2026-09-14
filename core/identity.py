"""Stable identifiers shared by job sources and persistence."""

import hashlib


def job_fingerprint(company: str, title: str, location: str) -> str:
    """Deduplicate equivalent listings regardless of which source found them."""
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def should_refresh_from_source(existing_source: str, incoming_source: str) -> bool:
    """Keep official career data authoritative over later aggregator copies."""
    existing_is_direct = (existing_source or "").startswith("company_careers:")
    incoming_is_direct = (incoming_source or "").startswith("company_careers:")
    return incoming_is_direct or not existing_is_direct
