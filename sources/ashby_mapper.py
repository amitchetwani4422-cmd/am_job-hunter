"""Pure mapping helpers for Ashby's public job-board response."""


def is_open_ashby_posting(item: dict) -> bool:
    """Ashby omits the flags on some boards; explicit closed flags always win."""
    return item.get("isListed") is not False and item.get("isArchived") is not True


def map_ashby_posting(item: dict, company: dict) -> dict:
    """Map one complete official posting into normalized Job constructor data."""
    location = item.get("location", "")
    if isinstance(location, dict):
        location = location.get("name", "")

    secondary = item.get("secondaryLocations") or []
    secondary_names = []
    for value in secondary:
        name = value.get("name", "") if isinstance(value, dict) else str(value)
        if name and name != location:
            secondary_names.append(name)
    if secondary_names:
        location = ", ".join([location, *secondary_names] if location else secondary_names)

    compensation = item.get("compensation")
    salary = ""
    if isinstance(compensation, dict):
        summary = compensation.get("summaryComponents") or []
        if summary:
            salary = " ".join(str(part) for part in summary)

    slug = company["ats_slug"]
    return {
        "title": item.get("title", ""),
        "company": company["name"],
        "location": location or "Location not specified",
        "description": item.get("descriptionHtml", "") or item.get("descriptionPlain", ""),
        "url": item.get("applyUrl", "") or item.get("externalLink", "") or item.get("jobUrl", ""),
        "source": company.get("source_name") or f"ashby:{slug}",
        "posted_date": item.get("publishedAt", "") or item.get("publishedDate", ""),
        "salary": salary,
        "job_type": item.get("employmentType", "") or "",
        "company_domain": company.get("domain", ""),
    }
