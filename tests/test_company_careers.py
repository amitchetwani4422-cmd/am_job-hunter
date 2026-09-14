import unittest
import json
from datetime import datetime, timezone
from pathlib import Path

from core.identity import job_fingerprint, should_refresh_from_source
from core.scorer import score_job
from sources.ashby_mapper import is_open_ashby_posting, map_ashby_posting
from sources.company_registry import TARGET_COMPANY_CAREERS
from tests.test_scorer import profile


class CompanyCareerMappingTests(unittest.TestCase):
    def _fixture(self, name: str) -> dict:
        path = Path(__file__).parent / "fixtures" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_openai_india_remote_posting_is_preserved_and_eligible(self):
        openai = next(company for company in TARGET_COMPANY_CAREERS if company["name"] == "OpenAI")
        payload = {
            "title": "Deployment Strategy Lead",
            "location": "India - Remote",
            "descriptionHtml": (
                "<p>Own enterprise AI deployment and implementation strategy for enterprise customers. "
                "Lead cross-functional product delivery and executive stakeholder relationships. "
                "Requires 8+ years of relevant experience.</p>"
            ),
            "publishedAt": "2026-09-12T08:30:00+00:00",
            "applyUrl": "https://jobs.ashbyhq.com/openai/example/application",
            "jobUrl": "https://jobs.ashbyhq.com/openai/example",
            "employmentType": "FullTime",
            "isListed": True,
        }

        job = map_ashby_posting(payload, openai)
        self.assertEqual(job["company"], "OpenAI")
        self.assertEqual(job["title"], payload["title"])
        self.assertEqual(job["location"], "India - Remote")
        self.assertEqual(job["description"], payload["descriptionHtml"])
        self.assertEqual(job["posted_date"], payload["publishedAt"])
        self.assertEqual(job["url"], payload["applyUrl"])
        self.assertEqual(job["source"], "company_careers:ashby:openai")

        result = score_job(
            job["title"], job["description"], job["location"], profile(),
            job["posted_date"], datetime(2026, 9, 14, tzinfo=timezone.utc),
        )
        self.assertEqual(result["remote_india_eligibility"], "Eligible")
        self.assertEqual(result["eligibility_confidence"], "High")

    def test_direct_and_aggregated_copy_share_fingerprint(self):
        direct = job_fingerprint("OpenAI", "Deployment Strategy Lead", "India - Remote")
        aggregate = job_fingerprint(" openai ", "deployment strategy lead", "india - remote")
        self.assertEqual(direct, aggregate)

    def test_direct_source_remains_authoritative_over_aggregator_copy(self):
        self.assertFalse(should_refresh_from_source("company_careers:ashby:openai", "jsearch"))
        self.assertTrue(should_refresh_from_source("jsearch", "company_careers:ashby:openai"))

    def test_target_registry_prioritizes_openai_and_elevenlabs(self):
        self.assertEqual([item["name"] for item in TARGET_COMPANY_CAREERS[:2]], ["OpenAI", "ElevenLabs"])

    def test_explicitly_unlisted_or_archived_roles_are_not_open(self):
        self.assertFalse(is_open_ashby_posting({"isListed": False}))
        self.assertFalse(is_open_ashby_posting({"isArchived": True}))
        self.assertTrue(is_open_ashby_posting({"isListed": True, "isArchived": False}))

    def test_live_validation_role_fixtures_are_all_mapped(self):
        expected = {
            "OpenAI": {"Strategy & Operations Lead - India"},
            "ElevenLabs": {
                "Deployment Strategist - India",
                "Deployment Strategist Lead - India",
            },
        }
        fixtures = {
            "OpenAI": "openai_ashby_jobs.json",
            "ElevenLabs": "elevenlabs_ashby_jobs.json",
        }
        for company_name, fixture_name in fixtures.items():
            company = next(c for c in TARGET_COMPANY_CAREERS if c["name"] == company_name)
            company = {**company, "ats_slug": company["ats_slugs"][0]}
            mapped = [
                map_ashby_posting(item, company)
                for item in self._fixture(fixture_name)["jobs"]
                if is_open_ashby_posting(item)
            ]
            self.assertEqual({job["title"] for job in mapped}, expected[company_name])
            for job in mapped:
                self.assertTrue(job["description"])
                self.assertTrue(job["location"])
                self.assertTrue(job["posted_date"])
                self.assertTrue(job["url"])
                self.assertTrue(job["external_job_id"])
                self.assertEqual(job["remote_status"], "Remote")

        elevenlabs = [
            map_ashby_posting(item, {**TARGET_COMPANY_CAREERS[1], "ats_slug": "elevenlabs"})
            for item in self._fixture("elevenlabs_ashby_jobs.json")["jobs"]
        ]
        self.assertEqual(elevenlabs[0]["location"], "Remote, India, Bengaluru, India")
        self.assertNotIn("utm_source", elevenlabs[0]["url"])


if __name__ == "__main__":
    unittest.main()
