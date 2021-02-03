from datetime import timedelta

from astropy.time import Time, TimeDelta
from django.views.generic import TemplateView

from exotom.models import Transit


class TransitsView(TemplateView):
    template_name = "transits.html"

    def __init__(self, *args, **kwargs):
        TemplateView.__init__(self, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # get now
        now = Time.now()

        # get transits
        transits = Transit.objects.filter(end__gte=now.datetime)

        # sort and return
        return {"transits": transits.order_by("start")}


class TransitObservationDetailView(TemplateView):
    template_name = "transitobservationdetails.html"

    def __init__(self, *args, **kwargs):
        TemplateView.__init__(self, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # get transit
        transit = Transit.objects.get(
            target_id=kwargs["target"], number=kwargs["transit"]
        )
        target = transit.target
        uncertainty_in_mins = transit.uncertainty_in_days() * 1440

        # calculate times
        times = {
            "start": {
                "earliest": transit.start_earliest(),
                "latest": transit.start_latest(),
            },
            "mid": {
                "earliest": transit.mid_earliest(),
                "latest": transit.mid_latest(),
            },
            "end": {
                "earliest": transit.end_earliest(),
                "latest": transit.end_latest(),
            },
        }

        # sort and return
        return {
            "transit": transit,
            "times": times,
            "uncertainty_in_mins": uncertainty_in_mins,
        }
