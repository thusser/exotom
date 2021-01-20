import traceback

from django.core.management.base import BaseCommand

from exotom.settings import FACILITIES
from exotom.ofi.iagtransit import IAGTransitForm
from tom_iag.iag import IAGFacility, get_instruments
from exotom.models import Target, Transit

from exotom.transits import calculate_transits_during_next_n_days
from exotom.exposure_calculator import calculate_exposure_time
from astropy.time import Time
import pytz



class Command(BaseCommand):
    help = 'Submit all transits that can be observed in the following night to telescope scheduler.'

    def handle(self, *args, **options):
        now = Time.now()

        targets = Target.objects.all()

        sites_instrument_types = FACILITIES['IAGTransit']['instruments']

        instruments = get_instruments()

        for target in targets:

            calculate_transits_during_next_n_days(target, n_days=1)

            transits_for_target = Transit.objects.filter(target=target, start__gt=now.datetime.astimezone(pytz.utc))

            for site_name, instrument_type in sites_instrument_types.items():
                instrument = instruments[instrument_type]

                for transit in transits_for_target:
                    if transit.observable_at_site(site=site_name):
                        try:
                            submit_transit_to_instrument(transit, instrument_type, instrument)
                        except Exception as e:
                            print(f"Error when submitting transit observation to instrument")
                            print(traceback.format_exc())


def submit_transit_to_instrument(transit: Transit, instrument_type: str, instrument: dict):
    print(f"Submitting transit {transit} with transit id {transit.id} and target id {transit.target_id}")

    magnitude = transit.target.targetextra_set.get(key='Mag (TESS)').float_value
    exposure_time = calculate_exposure_time(magnitude)

    data = {
        'facility': 'IAGTransit',
        'instrument_type': instrument_type,
        'transit': transit.number,
        'target_id': transit.target_id,
        'ipp_value': 1.05,
        'exposure_time': exposure_time,
        'readout_mode': instrument['modes']['readout']['modes'][0]['code'],
        'filter': instrument['optical_elements']['filters'][0]['code'],
    }
    form = IAGTransitForm(initial=data, data=data)
    form.is_valid()
    facility = IAGFacility()
    facility.submit_observation(form.observation_payload())

