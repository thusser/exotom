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

        # error
        T0_err = target.extra_fields["Epoch (BJD) err"]
        p_err = target.extra_fields["Period (days) err"]
        err = T0_err + transit.number * p_err

        # calculate times
        times = {
            "start": {
                "earliest": transit.start - timedelta(days=err),
                "latest": transit.start + timedelta(days=err),
            },
            "mid": {
                "earliest": transit.mid - timedelta(days=err),
                "latest": transit.mid + timedelta(days=err),
            },
            "end": {
                "earliest": transit.end - timedelta(days=err),
                "latest": transit.end + timedelta(days=err),
            },
        }

        # sort and return
        return {"transit": transit, "times": times, "uncertainty": err * 1440}
