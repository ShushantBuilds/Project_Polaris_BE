import os
import sys
import threading
from django.apps import AppConfig

class DiscoveryEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'discovery_engine'

    def ready(self):
        is_dev_server = 'runserver' in sys.argv
        is_gunicorn = any('gunicorn' in arg for arg in sys.argv)
        if is_dev_server and os.environ.get('RUN_MAIN') != 'true':
            return
        if not is_dev_server and not is_gunicorn:
            return

        from . import scheduler
        threading.Timer(2.0, scheduler.start).start()