import traceback

from django.core.management.base import BaseCommand
from tom_observations.models import ObservationRecord


from exotom.observation_downloader import TransitObservationDownloader
from exotom.transit_processor import TransitProcessor
from exotom.management.commands.update_observation_status import (
    update_observation_status_command,
)


class Command(BaseCommand):
    help = "Submit all transits that can be observed in the following night to telescope scheduler."

    def handle(self, *args, **options):
        process_new_observations_command()


def process_new_observations_command():
    update_observation_status_command()

    for observation_record in ObservationRecord.objects.all():
        try:
            downloader = TransitObservationDownloader(observation_record)
            if (
                downloader.observation_record_completed_and_all_lightcurve_dataproduct_not_created()
            ):
                all_lightcurves_dp = (
                    downloader.attempt_create_all_lightcurves_dataproduct()
                )
                processor = TransitProcessor(all_lightcurves_dp)
                processor.process()
        except Exception as e:
            print(f"Transit analysis failed because of '{e}'. Traceback:")
            traceback.print_exc()
