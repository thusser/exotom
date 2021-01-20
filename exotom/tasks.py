from tom_targets.models import Target

from exotom.management.commands.submit_transit_observations import submit_all_transits
from exotom.transits import calculate_transits_during_next_n_days
from exotom.celery import app


@app.task
def update():
    # calculate transits for next 24 hours
    for target in Target.objects.all():
        calculate_transits_during_next_n_days(target, 1)

    # submit observable transits
    submit_all_transits()
