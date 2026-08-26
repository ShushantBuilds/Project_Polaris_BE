# discovery_engine/management/commands/ingest_papers.py
import requests
from django.core.management.base import BaseCommand
from discovery_engine.models import Tag, ContentItem

OPENALEX_BASE_URL = "https://api.openalex.org/works"
CONTACT_EMAIL = "shushant19102000@gmail.com" 

RESEARCH_FIELDS = [
    "Computer Science",
    "Biology",
    "Physics",
    "Medicine",
    "Psychology",
    "Environmental Science",
    "Economics",
    "Engineering",
]

PAPERS_PER_FIELD = 15


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""
    position_map = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_map[pos] = word
    return " ".join(position_map[i] for i in sorted(position_map))


class Command(BaseCommand):
    help = "Ingests recent research papers from the OpenAlex API into ContentItem."

    def handle(self, *args, **options):
        total_added = 0
        for field_name in RESEARCH_FIELDS:
            tag, _ = Tag.objects.get_or_create(name=field_name, category='GENRE')
            added = self.ingest_field(field_name, tag)
            total_added += added
            self.stdout.write(f"{field_name}: added {added} new papers")
        self.stdout.write(self.style.SUCCESS(f"Done — {total_added} new papers ingested total."))

    def ingest_field(self, field_name, tag):
        params = {
            'search': field_name,
            'sort': 'publication_date:desc',
            'per_page': PAPERS_PER_FIELD,
            'mailto': CONTACT_EMAIL,
        }
        try:
            response = requests.get(OPENALEX_BASE_URL, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stderr.write(f"Failed to fetch {field_name}: {e}")
            return 0

        added = 0
        for work in response.json().get('results', []):
            external_id = work.get('id')
            if not external_id or ContentItem.objects.filter(external_id=external_id).exists():
                continue

            title = (work.get('title') or 'Untitled')[:500]
            abstract = reconstruct_abstract(work.get('abstract_inverted_index'))
            url = (work.get('primary_location') or {}).get('landing_page_url') or work.get('doi') or ''

            item = ContentItem.objects.create(
                title=title,
                description=abstract[:2000] if abstract else 'No abstract available.',
                url=url,
                external_id=external_id,
            )
            item.tags.add(tag)
            added += 1
        return added