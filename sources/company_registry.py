"""Dependency-free configuration for curated official career sources."""

TARGET_COMPANY_CAREERS = [
    {
        "key": "openai",
        "name": "OpenAI",
        "domain": "openai.com",
        "careers_url": "https://openai.com/careers/search/",
        "ats_platform": "ashby",
        "ats_slugs": ["openai"],
        "source_name": "company_careers:ashby:openai",
    },
    {
        "key": "elevenlabs",
        "name": "ElevenLabs",
        "domain": "elevenlabs.io",
        "careers_url": "https://elevenlabs.io/careers",
        "ats_platform": "ashby",
        "ats_slugs": ["elevenlabs", "eleven-labs"],
        "source_name": "company_careers:ashby:elevenlabs",
    },
]


def get_target_company(company_key: str) -> dict | None:
    normalized = company_key.strip().lower().replace("-", "")
    return next(
        (company for company in TARGET_COMPANY_CAREERS
         if company["key"].replace("-", "") == normalized
         or company["name"].lower().replace("-", "") == normalized),
        None,
    )
