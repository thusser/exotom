import datetime

from django import template
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

register = template.Library()


@register.inclusion_tag("exotom/partials/whats_new.html")
def whats_new():

    shown_period_in_hours = 48

    now_minus_period_hours = datetime.datetime.now() - datetime.timedelta(
        hours=shown_period_in_hours
    )
    recent_observation_records = ObservationRecord.objects.filter(
        scheduled_start__gt=now_minus_period_hours
    )

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
        "shown_period_in_hours": shown_period_in_hours,
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
