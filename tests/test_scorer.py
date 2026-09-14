import unittest
from datetime import datetime, timedelta, timezone
from core.scorer import assess_experience, check_india_friendly, score_job


def profile():
    return {
        "search": {
            "title_keywords_positive": ["ai deployment", "head of", "business operations", "growth", "adoption", "forward deployed", "strategic programs", "special projects", "solutions lead", "chief of staff"],
            "title_keywords_negative": ["software engineer", "developer", "data scientist", "project manager"],
            "relevant_tech": ["generative ai", "llm", "enterprise ai", "product delivery", "scaling operations"],
        },
        "scoring": {
            "candidate_years": 8,
            "strengths": ["generative ai", "ai agents", "llm", "enterprise ai", "product delivery", "scaling operations", "stakeholder management"],
            "leadership_signals": ["cross-functional", "team leadership", "poc to production"],
            "role_families": {
                "AI Deployment / Transformation": ["ai deployment", "ai adoption", "enterprise ai", "production deployment"],
                "Customer Success / Adoption / Retention": ["customer adoption", "retention and expansion", "customer success", "executive relationships"],
                "Implementation / Deployment": ["customer deployments", "implementation strategy", "production deployment"],
                "Strategy & Operations": ["operating strategy", "scalable operating processes", "strategic planning"],
                "Program / Delivery Leadership": ["strategic programs", "program delivery", "delivery roadmap"],
                "GTM / Growth Operations": ["growth operations", "go-to-market", "retention and expansion"],
                "Strategic Customer / Enterprise Programs": ["enterprise customers", "strategic customers", "executive relationships"],
                "Business Operations": ["business operations"],
            },
            "business_outcome_signals": ["adoption", "retention", "expansion", "customer outcomes", "operational efficiency"],
            "outside_scope_signals": ["write production code", "design and implement software", "individual contributor"],
            "seniority_titles": {"Head": ["head of"], "Director": ["director"], "Lead": ["lead"]},
        },
        "location": {
            "india_negative": ["us only", "canada only", "uk only", "eu only"],
        },
    }


class ExperienceTests(unittest.TestCase):
    def test_six_to_nine_and_eight_plus_are_strong(self):
        self.assertEqual(assess_experience("Requires 6-9 years")["compatibility"], "Strong Match")
        self.assertEqual(assess_experience("Requires 8+ years")["compatibility"], "Strong Match")

    def test_hard_ten_plus_is_a_gap_unless_equivalence_allowed(self):
        self.assertIn("hard 10+", assess_experience("Minimum 10+ years required")["compatibility"])
        self.assertIn("equivalent experience allowed", assess_experience("10+ years or equivalent experience")["compatibility"])


class EligibilityTests(unittest.TestCase):
    def test_explicit_india_remote_is_eligible(self):
        result = check_india_friendly("India - Remote", "", profile())
        self.assertEqual(result["eligibility"], "Eligible")
        self.assertEqual(result["confidence"], "High")

    def test_country_restricted_and_hybrid_are_ineligible(self):
        self.assertEqual(check_india_friendly("Remote - US only", "", profile())["eligibility"], "Ineligible")
        self.assertEqual(check_india_friendly("Hybrid, Bengaluru", "", profile())["eligibility"], "Ineligible")

    def test_ambiguous_remote_needs_verification(self):
        result = check_india_friendly("Remote", "Join our distributed team", profile())
        self.assertEqual(result["eligibility"], "Needs Verification")
        self.assertEqual(result["confidence"], "Low")


class FitTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 14, tzinfo=timezone.utc)
        self.description = (
            "Remote from India. Requires 8+ years. Lead cross-functional enterprise AI deployment, "
            "generative AI, AI agents and LLM programs from POC to production, including stakeholder management, "
            "team leadership, product delivery and scaling operations."
        )

    def test_strong_current_target_role_has_explainable_fields(self):
        result = score_job("Head of AI Deployment", self.description, "India - Remote", profile(),
                           "2026-09-12T00:00:00+00:00", self.now)
        self.assertGreaterEqual(result["score"], 70)
        self.assertEqual(result["remote_india_eligibility"], "Eligible")
        self.assertEqual(result["role_family"], "AI Deployment / Transformation")
        self.assertEqual(result["seniority"], "Head")
        self.assertEqual(result["experience_requirement"], "8+ years")
        self.assertTrue(result["reasons"])
        self.assertIn(result["resume_modification_recommended"], (True, False))

    def test_fit_and_hard_location_eligibility_are_separate(self):
        result = score_job("Head of AI Deployment", self.description, "Remote - US only", profile(),
                           "2026-09-12T00:00:00+00:00", self.now)
        self.assertGreaterEqual(result["score"], 70)
        self.assertEqual(result["remote_india_eligibility"], "Ineligible")

    def test_recency_does_not_change_core_fit_and_hard_ten_plus_is_low_fit(self):
        old = (self.now - timedelta(days=40)).isoformat()
        old_result = score_job("Head of AI Deployment", self.description, "India - Remote", profile(), old, self.now)
        fresh_result = score_job("Head of AI Deployment", self.description, "India - Remote", profile(),
                                 "2026-09-12T00:00:00+00:00", self.now)
        ten_result = score_job("Director AI Deployment", "Remote from India. Minimum 10+ years required. Lead AI deployment.",
                               "India - Remote", profile(), "2026-09-12T00:00:00+00:00", self.now)
        self.assertEqual(old_result["score"], fresh_result["score"])
        self.assertEqual(old_result["posted_age_days"], 40)
        self.assertLess(ten_result["score"], 55)

    def test_ten_plus_can_remain_a_stretch_when_responsibilities_strongly_align(self):
        result = score_job("Director AI Deployment", self.description.replace("8+", "10+"),
                           "India - Remote", profile(), "2026-09-12T00:00:00+00:00", self.now)
        self.assertIn("responsibilities strongly align", result["experience_compatibility"])
        self.assertGreaterEqual(result["score"], 55)

    def test_excluded_ic_role_is_not_recommended(self):
        result = score_job("Senior Software Engineer", "Remote from India. Write production code as an individual contributor and design and implement software. Requires 8+ years.", "India - Remote", profile(),
                           "2026-09-12T00:00:00+00:00", self.now)
        self.assertLess(result["score"], 55)
        self.assertTrue(result["important_gaps"])

    def test_unusual_titles_are_classified_from_responsibilities(self):
        cases = [
            ("Growth & Retention Lead", "Own enterprise customer adoption, retention and expansion, executive relationships, customer deployments and scalable operating processes.", "Customer Success / Adoption / Retention"),
            ("Adoption Specialist", "Lead AI adoption, customer adoption, implementation strategy, executive relationships and customer deployments.", "Customer Success / Adoption / Retention"),
            ("Forward Deployed", "Own AI deployment and production deployment for enterprise customers and strategic customers.", "AI Deployment / Transformation"),
            ("Strategic Programs", "Lead strategic programs, program delivery, strategic planning and a delivery roadmap.", "Program / Delivery Leadership"),
            ("Special Projects", "Own strategic planning, operating strategy and scalable operating processes across the business.", "Strategy & Operations"),
            ("Solutions Lead", "Lead enterprise AI adoption, implementation strategy and production deployment for enterprise customers.", "AI Deployment / Transformation"),
            ("Chief of Staff", "Own operating strategy, strategic planning, business operations and operational efficiency with executives.", "Strategy & Operations"),
        ]
        for title, description, expected in cases:
            with self.subTest(title=title):
                result = score_job(title, description + " Requires 8+ years. Remote from India.", "India - Remote", profile(), "2026-09-12T00:00:00+00:00", self.now)
                self.assertEqual(result["role_family"], expected)
                self.assertTrue(result["responsibility_evidence"])
                self.assertIn(expected, result["role_family_scores"])

    def test_negative_title_does_not_exclude_target_responsibilities(self):
        result = score_job("Software Engineer, Customer AI", self.description, "India - Remote", profile(),
                           "2026-09-12T00:00:00+00:00", self.now)
        self.assertGreaterEqual(result["score"], 55)
        self.assertFalse(any("outside-target" in gap for gap in result["important_gaps"]))

    def test_title_cannot_manufacture_capability_or_responsibility_points(self):
        result = score_job(
            "Head of Enterprise AI Generative AI LLM Product Delivery Cross-Functional Team Leadership",
            "Requires 8+ years. Remote from India.",
            "India - Remote", profile(), "2026-09-12T00:00:00+00:00", self.now,
        )
        self.assertEqual(result["score"], 20)  # 15 experience + 5 title only
        self.assertEqual(result["responsibility_evidence"], [])
        self.assertFalse(any(reason.startswith("Relevant strengths") for reason in result["reasons"]))

    def test_title_changes_core_fit_by_at_most_five_points(self):
        description = "Lead AI adoption and implementation strategy for enterprise customers. Requires 8+ years. Remote from India."
        familiar = score_job("Head of AI Deployment", description, "India - Remote", profile(), "2026-09-12T00:00:00+00:00", self.now)
        unfamiliar = score_job("Pathfinder", description, "India - Remote", profile(), "2026-09-12T00:00:00+00:00", self.now)
        self.assertLessEqual(abs(familiar["score"] - unfamiliar["score"]), 5)
        self.assertEqual(familiar["responsibility_evidence"], unfamiliar["responsibility_evidence"])


if __name__ == "__main__":
    unittest.main()
