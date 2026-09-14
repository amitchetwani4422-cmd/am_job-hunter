"""Ashby ATS — free public API, no auth needed.
API: GET https://api.ashbyhq.com/posting-api/job-board/{slug}
"""

import httpx
from sources.base import BaseSource
from core.models import Job
from sources.ashby_mapper import is_open_ashby_posting, map_ashby_posting


class AshbySource(BaseSource):
    name = "ashby"

    def __init__(self, company: dict):
        self.company = company
        self.slug = company["ats_slug"]
        self.name = company.get("source_name") or f"ashby:{self.slug}"

    async def fetch(self) -> list[Job]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.slug}"

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params={"includeCompensation": "true"})
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception:
                return []

        jobs = []
        for item in data.get("jobs", []):
            if not is_open_ashby_posting(item):
                continue
            # Do not filter titles here: ingest the official board in full and
            # let the shared description-first scorer decide relevance.
            jobs.append(Job(**map_ashby_posting(item, self.company)))
        return jobs
