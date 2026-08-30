import json
from mistralai.client import Mistral
from django.conf import settings
from .models import Tag

ENRICHMENT_PROMPT = """You are analyzing an academic paper abstract. Respond with ONLY a valid JSON object (no other text, no markdown formatting) with these exact keys:
- "summary": a 2-3 sentence plain-language summary a non-expert could understand
- "difficulty": one of "Beginner", "Intermediate", or "Advanced"
- "tags": a list of 2-4 short, specific topical tags (subfields, not the broad field itself)

Title: {title}
Abstract: {abstract}"""


def enrich_content_item(item):
    prompt = ENRICHMENT_PROMPT.format(title=item.title, abstract=item.description)
    with Mistral(api_key=settings.MISTRAL_API_KEY) as client:
        response = client.chat.complete(
            model="mistral-small-latest",  # small, fast, cheap — right-sized for bulk structured extraction
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
    raw_text = response.choices[0].message.content
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return  # skip silently rather than crash the whole batch on one malformed response

    item.ai_summary = data.get('summary', '')[:1000]
    item.save(update_fields=['ai_summary'])

    difficulty = data.get('difficulty')
    if difficulty in ('Beginner', 'Intermediate', 'Advanced'):
        tag, _ = Tag.objects.get_or_create(name=difficulty, category='DIFFICULTY')
        item.tags.add(tag)

    for tag_name in data.get('tags', [])[:4]:
        tag_name = tag_name.strip()
        if tag_name:
            tag = Tag.objects.filter(name__iexact=tag_name, category='GENRE').first() \
                  or Tag.objects.create(name=tag_name, category='GENRE')
            item.tags.add(tag)