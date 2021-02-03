from astropy.time import Time
from django import forms, template
from exotom.ofi.iagtransit import SETTINGS

from exotom.models import Transit

register = template.Library()


@register.inclusion_tag("tom_iag/partials/target_transits.html")
def transits(target):
    """
    Collect the transits for a given target and pass them to the transits.html partial template.
    :return:
    """

    # get time
    now = Time.now()

    # get future transits
    prediction = Transit.objects.filter(target=target, end__gt=now.isot)

    return {"target": target, "prediction": prediction}


@register.inclusion_tag("tom_iag/partials/transit_observing_buttons.html")
def transit_observing_buttons(transit):
    """
    Displays the observation buttons for transits.
    """

    # abbrevations
    abbr = {"McDonald": "N", "Sutherland": "S", "Göttingen": "G"}

    # get list with sites
    sites = [
        (f[1], SETTINGS["instruments"][f[1]], abbr[f[1]]) for f in transit.facilities
    ]

    # return it
    return {
        "target": transit.target,
        "facility": "IAGTransit",
        "transit": transit,
        "sites": sites,
    }
