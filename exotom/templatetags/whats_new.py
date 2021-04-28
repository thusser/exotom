import datetime

from django import template
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from exotom.models import Transit

register = template.Library()


def get_observation_record_datetime(obs_record):
    if obs_record.scheduled_start:
        return obs_record.scheduled_start
    else:
        try:
            return Transit.objects.get(
                target__id=obs_record.parameters["target_id"],
                number=obs_record.parameters["transit"],
            ).start
        except:
            return obs_record.created


@register.inclusion_tag("exotom/partials/whats_new.html")
def whats_new(n_most_recent_observations=5):

    recent_observation_records = ObservationRecord.objects.filter(
        scheduled_start__isnull=False
    )
    recent_observation_records = sorted(
        recent_observation_records,
        key=get_observation_record_datetime,
        reverse=True,
    )
    if n_most_recent_observations <= len(recent_observation_records):
        recent_observation_records = recent_observation_records[
            :n_most_recent_observations
        ]
    else:
        n_most_recent_observations = len(recent_observation_records)

    recent_observations = []
    for obs_record in recent_observation_records:
        try:
            url = DataProduct.objects.get(
                observation_record=obs_record, data_product_type="image_file"
            ).data.url
        except DataProduct.DoesNotExist as e:
            print(e)
            url = ""

        recent_observations.append({"observation_record": obs_record, "image_url": url})

    return {
        "n_most_recent_observations": n_most_recent_observations,
        "recent_observations": recent_observations,
    }


@register.filter
def get_target_extra(target, key):
    print(f"'{key}'")
    try:
        return str(target.targetextra_set.get(key=key).value)
    except Exception as e:
        print(e)
        return ""
