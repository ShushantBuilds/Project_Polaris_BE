from django.core.management.base import BaseCommand
from discovery_engine.ingestion import fetch_and_ingest

RESEARCH_FIELDS = [
    "Computer Science", "Biology", "Physics", "Medicine",
    "Psychology", "Environmental Science", "Economics", "Engineering",
    "Transformer Models", "CRISPR-Cas9", "Quantum Cryptography", "Behavioral Economics",
]
PAPERS_PER_FIELD = 15


class Command(BaseCommand):
    help = "Seeds a baseline content pool across broad fields, for new users before any search has happened."

    def handle(self, *args, **options):
        total = 0
        for field_name in RESEARCH_FIELDS:
            added = fetch_and_ingest(field_name, per_page=PAPERS_PER_FIELD, sort_by_recency=True, tag_with_query=True)
            total += added
            self.stdout.write(f"{field_name}: added {added} new papers")
        self.stdout.write(self.style.SUCCESS(f"Done — {total} new papers ingested total."))