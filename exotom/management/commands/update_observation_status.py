import traceback

from django.core.management import call_command
from django.core.management.base import BaseCommand
from tom_observations.models import ObservationRecord
from exotom.settings import FACILITIES, SITES
from exotom.ofi.iagtransit import IAGTransitForm
from tom_iag.iag import IAGFacility, get_instruments
from exotom.models import Target, Transit

from exotom.transits import calculate_transits_during_next_n_days
from exotom.exposure_calculator import calculate_exposure_time
from astropy.time import Time
import pytz


class Command(BaseCommand):
    help = "Submit all transits that can be observed in the following night to telescope scheduler."

    def handle(self, *args, **options):
        update_observation_status_command()


def update_observation_status_command():
    for target in Target.objects.all():
        call_command("updatestatus", target_id=target.id)

    # delete
    for obs_record in ObservationRecord.objects.all():
        if obs_record.status in ["CANCELED", "WINDOW_EXPIRED"]:
            obs_record.delete()
