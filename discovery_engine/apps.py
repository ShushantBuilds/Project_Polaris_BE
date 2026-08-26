import os
from django.apps import AppConfig

class DiscoveryEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'discovery_engine'

    def ready(self):
        if os.environ.get('RUN_MAIN') != 'true':
            return  
        from . import scheduler
        scheduler.start()