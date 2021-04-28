import argparse
from datetime import datetime, timedelta

# python ./targets/create_observation_record_and_transit.py --observation_id 2 --target_name 1809  --start_date 2021 3 5 15
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

from exotom.models import Transit
from exotom.transits import calculate_transits_during_next_n_days


def create_observation_record_and_transit(
    observation_id: int,
    target_name: str,
    transit_number: int,
    contact: str = "",
    start_date_list: [int] = None,
):
    """Create database objects for a transit observation submitted from a different ExoTOM instance.

    When observations were submitted from a different ExoTom instance, the ObservationRecord and Transit
    database objects are missing (assuming the target object actually exists).
    So if you want to run the analysis on a different instance you have
    to create the Transit object (done here by calling the calculate_transits_during_next_n_days function)
    and then the ObservationRecord.

    All necessary parameters can be taken from the observation request page or the obsevation status page.

    :param observation_id: "request id" in the observation portal
    :param target_name: str. part (eg "TOI 1809" or "1809") of the target name used to find the target object. Should be unique.
    :param transit_number: number of the transit (should be observation request name)
    :param contact: str = "". "INGRESS" or "EGRESS"
    :param start_date_list: [int] = None. date less than 24 hours before the transit as [year, month, day, hour]
        (eg [2021, 4, 3, 15]). If not given, now - 24 hours is used.
    """
    if start_date_list is None:
        start_time = datetime.now() - timedelta(hours=24)

    print(start_time, observation_id, target_name)

    target: Target = Target.objects.get(name__contains=target_name)
    calculate_transits_during_next_n_days(target, n_days=1, start_time=start_time)

    transit: Transit = Transit.objects.get(target=target, number=transit_number)

    oo = ObservationRecord.objects.create(
        target=target,
        facility="IAGTransit",
        observation_id=observation_id,
        parameters={
            "transit": transit_number,
            "transit_id": transit.id,
            "name": f"Target {target.name}, transit #{transit.number} " + contact,
        },
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--observation_id", type=int, required=True)
    parser.add_argument("--target_name", type=str, required=True)
    parser.add_argument("--transit_number", type=int, required=True)
    parser.add_argument(
        "--start_date", action="store", required=True, nargs=4, type=int
    )

    args = parser.parse_args()

    create_observation_record_and_transit(
        args.observation_id, args.target_name, args.transit_number, args.start_date
    )
