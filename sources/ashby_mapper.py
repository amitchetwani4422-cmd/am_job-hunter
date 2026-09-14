"""Pure mapping helpers for Ashby's public job-board response."""

from urllib.parse import urlsplit, urlunsplit


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

    slug = company.get("ats_slug") or (company.get("ats_slugs") or [""])[0]
    raw_url = item.get("applyUrl", "") or item.get("externalLink", "") or item.get("jobUrl", "")
    if raw_url:
        parts = urlsplit(raw_url)
        canonical_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    else:
        canonical_url = ""
    external_job_id = str(item.get("id") or item.get("jobId") or "")
    if not external_job_id and item.get("jobUrl"):
        external_job_id = urlsplit(item["jobUrl"]).path.rstrip("/").split("/")[-1]
    remote_status = str(item.get("workplaceType") or item.get("workplace_type") or "")
    if not remote_status and "remote" in location.lower():
        remote_status = "Remote"
    return {
        "title": item.get("title", ""),
        "company": company["name"],
        "location": location or "Location not specified",
        "description": item.get("descriptionHtml", "") or item.get("descriptionPlain", ""),
        "url": canonical_url,
        "external_job_id": external_job_id,
        "remote_status": remote_status,
        "source": company.get("source_name") or f"ashby:{slug}",
        "posted_date": item.get("publishedAt", "") or item.get("publishedDate", ""),
        "salary": salary,
        "job_type": item.get("employmentType", "") or "",
        "company_domain": company.get("domain", ""),
    }
