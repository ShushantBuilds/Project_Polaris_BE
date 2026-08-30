# discovery_engine/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django.core.management import call_command

def run_content_pipeline_job():
    call_command('ingest_papers')
    call_command('enrich_papers')
    call_command('prune_stale_tags')

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    scheduler.add_job(run_content_pipeline_job, trigger=IntervalTrigger(hours=6), id="content_pipeline_job", replace_existing=True)
    scheduler.start()