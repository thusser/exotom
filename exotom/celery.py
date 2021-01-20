import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exotom.settings')

app = Celery('exotom')
app.config_from_object('django.conf:settings')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# run update every day
app.conf.beat_schedule = {
    # Executes every day at 15:00
    'update': {
        'task': 'exotom.tasks.update',
        'schedule': crontab(hour=15, minute=0)
    }
}
