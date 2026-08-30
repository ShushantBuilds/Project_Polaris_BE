# discovery_engine/management/commands/prune_stale_tags.py
from django.core.management.base import BaseCommand
from discovery_engine.models import Tag

class Command(BaseCommand):
    help = "Deletes tags with zero associated content items AND zero users who selected them as a preference."

    def handle(self, *args, **options):
        orphaned = Tag.objects.filter(content_items__isnull=True, interested_users__isnull=True)
        count = orphaned.count()
        orphaned.delete()
        self.stdout.write(self.style.SUCCESS(f"Removed {count} unused tags."))