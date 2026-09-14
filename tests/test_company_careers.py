import unittest
from datetime import datetime, timezone

from core.identity import job_fingerprint, should_refresh_from_source
from core.scorer import score_job
from sources.ashby_mapper import is_open_ashby_posting, map_ashby_posting
from sources.company_careers import TARGET_COMPANY_CAREERS
from tests.test_scorer import profile


class CompanyCareerMappingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
