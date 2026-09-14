"""Curated official company career sources for the active search profile.

The source discovers the ATS slug from the official careers page and probes
configured aliases. Every open ATS posting is returned without title filtering;
the shared scorer remains the only relevance filter.
"""

import re

import httpx

from core.models import Job
from sources.ashby_mapper import is_open_ashby_posting, map_ashby_posting
from sources.base import BaseSource
from sources.company_registry import TARGET_COMPANY_CAREERS, get_target_company


ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"

def discover_ashby_slugs(html: str) -> list[str]:
    """Extract public Ashby organization slugs embedded in an official page."""
    patterns = (
        r"jobs\.ashbyhq\.com/([^/\"'?#\\]+)",
        r"posting-api/job-board/([^/\"'?#&\\]+)",
    )
    found = []
    for pattern in patterns:
        for slug in re.findall(pattern, html or "", flags=re.IGNORECASE):
            if slug not in found:
                found.append(slug)
    return found


class OfficialCompanyCareerSource(BaseSource):
    """Fetch a complete official Ashby board, with slug discovery/fallbacks."""

    def __init__(self, company: dict):
        self.company = company
        self.name = company["source_name"]
        self.diagnostics = {
            "company": company["name"],
            "source": self.name,
            "endpoints_used": [],
            "raw_jobs_fetched": 0,
            "jobs_parsed": 0,
            "jobs_skipped": {},
            "errors": [],
        }

    def _skip(self, reason: str) -> None:
        skipped = self.diagnostics["jobs_skipped"]
        skipped[reason] = skipped.get(reason, 0) + 1

    async def fetch(self) -> list[Job]:
        slugs = list(self.company.get("ats_slugs") or [])
        headers = {"User-Agent": "JobHunter/2.0 (+official-career-ingestion)"}
        postings: dict[str, dict] = {}

        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
            careers_url = self.company["careers_url"]
            try:
                response = await client.get(careers_url)
                response.raise_for_status()
                for slug in discover_ashby_slugs(response.text):
                    if slug not in slugs:
                        slugs.insert(0, slug)
            except Exception as exc:
                self.diagnostics["errors"].append(f"official page {careers_url}: {exc}")

            for slug in slugs:
                endpoint = ASHBY_API.format(slug=slug)
                try:
                    response = await client.get(endpoint, params={"includeCompensation": "true"})
                    response.raise_for_status()
                    payload = response.json()
                    raw_jobs = payload.get("jobs", [])
                    if not isinstance(raw_jobs, list):
                        self._skip(f"invalid jobs payload from {endpoint}")
                        continue
                    self.diagnostics["endpoints_used"].append(endpoint)
                    self.diagnostics["raw_jobs_fetched"] += len(raw_jobs)
                    for item in raw_jobs:
                        if not is_open_ashby_posting(item):
                            self._skip("unlisted or archived")
                            continue
                        mapped = map_ashby_posting(item, {
                            **self.company,
                            "ats_slug": slug,
                        })
                        if not mapped["title"] or not mapped["url"]:
                            self._skip("missing title or canonical URL")
                            continue
                        identity = mapped.get("external_job_id") or mapped["url"]
                        postings[identity] = mapped
                except Exception as exc:
                    self.diagnostics["errors"].append(f"ATS endpoint {endpoint}: {exc}")

        jobs = [Job(**posting) for posting in postings.values()]
        self.diagnostics["jobs_parsed"] = len(jobs)
        return jobs


def build_target_company_sources(company_key: str = None) -> list:
    companies = TARGET_COMPANY_CAREERS
    if company_key:
        company = get_target_company(company_key)
        companies = [company] if company else []
    return [OfficialCompanyCareerSource(company) for company in companies]
