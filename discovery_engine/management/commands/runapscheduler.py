from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util
from django.utils import timezone


def scheduled_ingest():
    """Fetches fresh OpenAlex papers across research fields every 6 hours."""
    print(f"\n[{timezone.now().strftime('%H:%M:%S')}] Executing scheduled OpenAlex paper ingestion...")
    call_command("ingest_papers")
    print(f"[{timezone.now().strftime('%H:%M:%S')}] Ingestion complete. Waiting for next schedule...")


def scheduled_prune_tags():
    """Cleans up orphaned tags once daily."""
    print(f"\n[{timezone.now().strftime('%H:%M:%S')}] Pruning unused tags...")
    call_command("prune_stale_tags")


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """Deletes APScheduler execution logs older than 7 days to keep the DB clean."""
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Runs APScheduler to execute background cron jobs."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # 1. Ingest papers every 6 hours (AND run once immediately on startup for testing)
        scheduler.add_job(
            scheduled_ingest,
            trigger=CronTrigger(hour="*/6"),
            id="scheduled_ingest",
            max_instances=1,
            replace_existing=True,
            next_run_time=timezone.now(),  # <--- THIS FORCES IT TO RUN IMMEDIATELY ON START
        )
        self.stdout.write(self.style.SUCCESS("Registered job: scheduled_ingest (every 6 hours)."))

        # 2. Prune unused tags daily at midnight
        scheduler.add_job(
            scheduled_prune_tags,
            trigger=CronTrigger(hour="00", minute="00"),
            id="scheduled_prune_tags",
            max_instances=1,
            replace_existing=True,
        )
        self.stdout.write(self.style.SUCCESS("Registered job: scheduled_prune_tags (daily at midnight)."))

        # 3. Weekly DB maintenance for APScheduler execution logs
        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        self.stdout.write(self.style.SUCCESS("Registered job: delete_old_job_executions (weekly)."))

        try:
            self.stdout.write(self.style.WARNING("Starting APScheduler daemon... (Press Ctrl+C to quit)"))
            scheduler.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.ERROR("\nStopping APScheduler..."))
            scheduler.shutdown()
            self.stdout.write(self.style.SUCCESS("APScheduler shutdown successfully."))