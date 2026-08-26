from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django.core.management import call_command

def run_ingestion_job():
    call_command('ingest_papers')

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    scheduler.add_job(run_ingestion_job, trigger=IntervalTrigger(hours=6), id="ingest_papers_job", replace_existing=True)
    scheduler.start()