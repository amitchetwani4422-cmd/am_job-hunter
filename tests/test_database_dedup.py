import importlib.util
import sys
import tempfile
import types
import unittest

if importlib.util.find_spec("dotenv") is None:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv_stub

from core import database


def job_record(job_id: str, source: str, description: str) -> dict:
    return {
        "id": job_id,
        "title": "Deployment Strategy Lead",
        "company": "OpenAI",
        "location": "India - Remote",
        "description": description,
        "url": "https://jobs.ashbyhq.com/openai/example/application",
        "source": source,
        "posted_date": "2026-09-12T08:30:00+00:00",
        "discovered_at": "2026-09-14T00:00:00+00:00",
        "tech_stack": "enterprise ai",
        "experience_level": "senior",
        "relevance_score": 75,
        "status": "new",
        "company_domain": "openai.com",
        "salary": "",
        "job_type": "FullTime",
        "india_friendly": "yes",
        "location_note": "Remote work from India explicitly allowed",
        "scored_profile_id": 1,
        "fit_classification": "Strong Fit",
        "remote_india_eligibility": "Eligible",
        "eligibility_confidence": "High",
        "experience_requirement": "8+ years",
        "experience_compatibility": "Strong Match",
        "seniority": "Lead",
        "role_family": "Implementation / Deployment",
        "secondary_role_families": "[]",
        "role_family_confidence": 80,
        "role_family_scores": "{}",
        "responsibility_evidence": "[]",
        "posted_age_days": 2,
        "match_reasons": "[]",
        "important_gaps": "[]",
        "resume_modification_recommended": 0,
    }


class DatabaseDeduplicationTests(unittest.TestCase):
    def test_url_match_updates_matched_row_and_keeps_direct_source_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            original_path = database.DB_PATH
            database.DB_PATH = f"{directory}/jobs.db"
            try:
                database.init_db()
                aggregate = job_record("aggregator-fingerprint", "jsearch", "Short aggregator copy")
                official = job_record(
                    "different-official-fingerprint",
                    "company_careers:ashby:openai",
                    "Complete official description",
                )

                self.assertEqual(database.insert_job(aggregate), "new")
                self.assertEqual(database.insert_job(official), "updated")
                database.insert_job({**aggregate, "description": "Later aggregator overwrite"})

                connection = database.get_connection()
                try:
                    rows = connection.execute("SELECT id, source, description FROM jobs").fetchall()
                finally:
                    connection.close()

                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["id"], "aggregator-fingerprint")
                self.assertEqual(rows[0]["source"], "company_careers:ashby:openai")
                self.assertEqual(rows[0]["description"], "Complete official description")
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
