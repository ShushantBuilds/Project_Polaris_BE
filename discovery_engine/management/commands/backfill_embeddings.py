from django.core.management.base import BaseCommand
from discovery_engine.models import ContentItem
from discovery_engine.embeddings import compute_embedding

class Command(BaseCommand):
    help = "Computes embeddings for ContentItems that don't have one yet."

    def handle(self, *args, **options):
        pending = ContentItem.objects.filter(embedding__isnull=True)
        count = 0
        for item in pending:
            item.embedding = compute_embedding(f"{item.title}. {item.description}")
            item.save(update_fields=['embedding'])
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Computed embeddings for {count} content items."))