"""Curated official company career sources for the active search profile.

Every configured board is fetched in full. Relevance is intentionally left to
the existing scorer rather than being approximated with title filters here.
"""

TARGET_COMPANY_CAREERS = [
    {
        "name": "OpenAI",
        "domain": "openai.com",
        "careers_url": "https://openai.com/careers/search/",
        "ats_platform": "ashby",
        "ats_slug": "openai",
        "source_name": "company_careers:ashby:openai",
    },
    {
        "name": "ElevenLabs",
        "domain": "elevenlabs.io",
        "careers_url": "https://elevenlabs.io/careers",
        "ats_platform": "ashby",
        "ats_slug": "elevenlabs",
        "source_name": "company_careers:ashby:elevenlabs",
    },
]


def build_target_company_sources() -> list:
    """Instantiate adapters for each configured official company board."""
    from sources.ashby import AshbySource

    adapters = {"ashby": AshbySource}
    return [adapters[company["ats_platform"]](company) for company in TARGET_COMPANY_CAREERS]
