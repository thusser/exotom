import traceback

from django.core.management.base import BaseCommand
from tom_observations.models import ObservationRecord

from exotom.settings import FACILITIES, SITES
from exotom.ofi.iagtransit import (
    IAGTransitForm,
    IAGTransitSingleContactForm,
    IAGTransitFacility,
)
from tom_iag.iag import IAGFacility, get_instruments
from exotom.models import Target, Transit

from exotom.transits import calculate_transits_during_next_n_days
from exotom.exposure_calculator import calculate_exposure_time
from astropy.time import Time
import pytz

from local_settings import MAX_EXPOSURES_PER_REQUEST


class Command(BaseCommand):
    help = "Submit all transits that can be observed in the following night to telescope scheduler."

    def handle(self, *args, **options):
        submit_all_transit_contacts()


def submit_all_transit_contacts():
    now = Time.now()

    targets = Target.objects.all().order_by("id")

    instruments = get_instruments()

    for target in targets:

        calculate_transits_during_next_n_days(target, n_days=1)

        transits_for_target = Transit.objects.filter(
            target=target, start__gt=now.datetime.astimezone(pytz.utc)
        )

        for site_name, site_info in SITES.items():
            instrument_type = site_info["instrument"]
            instrument_details = instruments[instrument_type]

            for transit in transits_for_target:
                submit_ingresses_egresses_for_transit(
                    instrument_details, instrument_type, site_name, transit
                )


def submit_ingresses_egresses_for_transit(
    instrument_details, instrument_type, site_name, transit
):
    if transit.ingress_observable_at_site(site=site_name):
        try:
            submit_transit_single_contact_to_instrument(
                transit, instrument_type, instrument_details, contact="INGRESS"
            )
        except Exception as e:
            print(f"Error when submitting transit observation to instrument")
            print(traceback.format_exc())

    if transit.egress_observable_at_site(site=site_name):
        try:
            submit_transit_single_contact_to_instrument(
                transit, instrument_type, instrument_details, contact="EGRESS"
            )
        except Exception as e:
            print(f"Error when submitting transit observation to instrument")
            print(traceback.format_exc())


def submit_transit_single_contact_to_instrument(
    transit: Transit, instrument_type: str, instrument_details: dict, contact: str
):
    observation_data = get_observation_data(
        transit, instrument_type, instrument_details, contact
    )

    form = IAGTransitSingleContactForm(initial=observation_data, data=observation_data)
    form.is_valid()
    observation_payload = form.observation_payload()

    facility = IAGTransitFacility()

    n_exposures = facility.get_number_of_exposures(observation_payload)
    if n_exposures > MAX_EXPOSURES_PER_REQUEST:
        raise Exception(
            f"{n_exposures} requested which is more than {MAX_EXPOSURES_PER_REQUEST}"
            f" max allowed per request."
        )

    print(
        f"Submitting transit {transit} with transit id {transit.id} and target id {transit.target_id}"
    )

    observation_ids = facility.submit_observation(observation_payload)

    # create observation record
    for observation_id in observation_ids:
        ObservationRecord.objects.create(
            target=transit.target,
            facility="IAGTransit",
            parameters=form.cleaned_data,
            observation_id=observation_id,
        )


def get_observation_data(
    transit: Transit, instrument_type: str, instrument_details: dict, contact: str
) -> dict:
    magnitude = transit.target.targetextra_set.get(key="Mag (TESS)").float_value
    exposure_time = calculate_exposure_time(magnitude, instrument_type)

    data = {
        "name": f"{transit.target.name} #{transit.number} {contact}",
        "facility": "IAGTransit",
        "instrument_type": instrument_type,
        "transit": transit.number,
        "transit_id": transit.id,
        "contact": contact,
        "target_id": transit.target_id,
        "ipp_value": get_ipp_value(transit),
        "max_airmass": 2.0,  # correspond to alt >= 30°
        "exposure_time": exposure_time,
        "readout_mode": instrument_details["modes"]["readout"]["modes"][0]["code"],
        "filter": instrument_details["optical_elements"]["filters"][0]["code"],
    }
    return data


def get_ipp_value(transit: Transit) -> float:
    return 0.5
