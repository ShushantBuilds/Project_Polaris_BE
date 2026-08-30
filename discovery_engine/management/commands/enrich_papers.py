from django.core.management.base import BaseCommand
from discovery_engine.models import ContentItem
from discovery_engine.ai_enrichment import enrich_content_item

BATCH_SIZE = 20

class Command(BaseCommand):
    help = "Enriches ContentItems missing an AI-generated summary using the Mistral API."

    def handle(self, *args, **options):
        pending = ContentItem.objects.filter(ai_summary__isnull=True)[:BATCH_SIZE]
        count = 0
        for item in pending:
            try:
                enrich_content_item(item)
                count += 1
            except Exception as e:
                self.stderr.write(f"Failed to enrich '{item.title}': {e}")
        self.stdout.write(self.style.SUCCESS(f"Enriched {count} content items."))