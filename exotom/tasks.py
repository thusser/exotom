from tom_targets.models import Target

from exotom.management.commands.process_new_observations import (
    process_new_observations_command,
)
from exotom.management.commands.submit_transit_observations import submit_all_transits
from exotom.management.commands.submit_transit_contact_observations import (
    submit_all_transit_contacts,
)
from exotom.management.commands.update_observation_status import (
    update_observation_status_command,
)
from exotom.transits import calculate_transits_during_next_n_days
from exotom.celery import app


@app.task
def submit_observations():
    # calculate transits for next 24 hours
    for target in Target.objects.all():
        calculate_transits_during_next_n_days(target, 1)

    # submit observable transits
    submit_all_transits()

    # submit just ingres/egress
    submit_all_transit_contacts()


@app.task
def update_observation_status():
    update_observation_status_command()


@app.task
def process_new_observations():
    process_new_observations_command()
