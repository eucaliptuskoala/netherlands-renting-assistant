import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

SYSTEM_PROMPT = """You are an expert Netherlands rental housing consultant and cover letter writer.
Your job is to generate a compelling, professional, and courteous rental application message
for Dutch estate agents (makelaars) and private landlords.

In the Dutch rental market, competition is fierce. Makelaars receive hundreds of inquiries.
To get invited for a viewing (bezichtiging), the inquiry MUST:
1. Be polite, concise, and structured.
2. Clearly state the applicant's name and status (student/working professional).
3. Confirm financial viability (salary, savings, guarantor, or scholarship satisfying the typical rent requirement).
4. Highlight ideal tenant qualities (non-smoker, no pets, reliable, quiet).
5. State the intended move-in date and rental duration.
6. Request a viewing opportunity.

Format Requirements:
- Provide BOTH a Dutch version (Nederlands) first, followed by an English version (English).
- Dutch makelaars strongly prefer Dutch messages, even from international tenants.
- Wrap each message inside a plain markdown code block so Telegram users can tap to copy in one click:
```
[Dutch Message Here]
```

```
[English Message Here]
```
Do not add conversational fluff before or after. Provide the copyable blocks with a short header.
"""


def _get_client() -> genai.Client | None:
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GEMINI_KEY')
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def generate_cover_letter(user_profile: dict[str, Any], listing: dict[str, Any]) -> str:
    """Generate tailored Dutch and English rental cover letters using Gemini."""
    client = _get_client()
    if not client:
        return '⚠️ Error: `GEMINI_API_KEY` is not set. Please add it to your environment variables.'

    name = user_profile.get('first_name') or 'Applicant'
    bio = user_profile.get('bio') or ''
    if not bio:
        return (
            '⚠️ You have not set up your profile bio yet!\n\n'
            'Please tap ⚙️ Settings -> 📝 Edit Bio to describe your status, income, '
            'and habits so Gemini can generate a personalized application.'
        )

    address = listing.get('address') or 'the property'
    city = (listing.get('city') or 'the Netherlands').title()
    price = listing.get('price')
    price_str = f'€{price}' if price else 'listed price'
    area = listing.get('living_area') or ''
    url = listing.get('url') or ''

    user_prompt = f"""Generate a rental inquiry / motivation letter for the following listing:

LISTING DETAILS:
- Address: {address}
- City: {city}
- Rent: {price_str} / month
- Living Area: {area}
- URL: {url}

APPLICANT PROFILE:
- Name: {name}
- Background & Bio: {bio}

Write the Dutch version first, then the English version.
Ensure all key selling points from the applicant's bio are seamlessly woven into the letter."""

    models_to_try = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.8-flash']
    last_error = None

    for model in models_to_try:
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                ),
            )
            if response.text:
                return response.text
        except Exception as e:
            last_error = e
            continue

    return f'⚠️ Gemini API error: {last_error}'
