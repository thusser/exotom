import logging
from django.db import models
from tom_targets.models import Target

from datetime import timedelta


log = logging.getLogger(__name__)


class Transit(models.Model):
    """A single transit."""

    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    number = models.IntegerField("Transit number")

    start = models.DateTimeField("Time the transit starts")
    mid = models.DateTimeField("Time of mid-transit")
    end = models.DateTimeField("Time the transit ends")

    def uncertainty_in_days(self):
        return (
            (self.target.extra_fields["Epoch (BJD) err"]) ** 2
            + (self.number * self.target.extra_fields["Period (days) err"]) ** 2
        ) ** 0.5

    def start_earliest(self):
        err = timedelta(days=self.uncertainty_in_days())
        return self.start - err

    def start_latest(self):
        err = timedelta(days=self.uncertainty_in_days())
        return self.start + err

    def mid_earliest(self):
        err = timedelta(days=self.uncertainty_in_days())
        return self.mid - err

    def mid_latest(self):
        err = timedelta(days=self.uncertainty_in_days())
        return self.mid + err

    def end_earliest(self):
        err = timedelta(days=self.uncertainty_in_days())
        return self.end - err

    def end_latest(self):
        err = timedelta(days=self.uncertainty_in_days())
        return self.end + err

    @property
    def facilities(self):
        return list(
            set(
                [
                    (td.facility, td.site)
                    for td in self.transitobservationdetails_set.all()
                    if td.visible
                ]
            )
        )

    def visible(self, facility):
        return any(
            [
                td.visible
                for td in self.transitobservationdetails_set.filter(facility=facility)
            ]
        )

    def ingress_visible(self, facility):
        return any(
            [
                td.ingress_visible
                for td in self.transitobservationdetails_set.filter(facility=facility)
            ]
        )

    def egress_visible(self, facility):
        return any(
            [
                td.egress_visible
                for td in self.transitobservationdetails_set.filter(facility=facility)
            ]
        )

    def visible_at_site(self, site):
        """Checks if transit is in the sky at the given site."""
        tds = self.transitobservationdetails_set.filter(site=site)
        visible = any([td.visible for td in tds])
        return visible

    def observable_at_site(self, site):
        """Checks if transit is in the sky at the given site and whether star is bright enough and transit deep enough."""
        tds = self.transitobservationdetails_set.filter(site=site)
        observable = any([td.observable for td in tds])
        return observable

    def ingress_visible_at_site(self, site):
        """Checks if transit is in the sky at the given site."""
        tds = self.transitobservationdetails_set.filter(site=site)
        visible = any([td.ingress_visible for td in tds])
        return visible

    def ingress_observable_at_site(self, site):
        """Checks if transit is in the sky at the given site and whether star is bright enough and transit deep enough."""
        tds = self.transitobservationdetails_set.filter(site=site)
        observable = any([td.ingress_observable for td in tds])
        return observable

    def egress_visible_at_site(self, site):
        """Checks if transit is in the sky at the given site."""
        tds = self.transitobservationdetails_set.filter(site=site)
        visible = any([td.egress_visible for td in tds])
        return visible

    def egress_observable_at_site(self, site):
        """Checks if transit is in the sky at the given site and whether star is bright enough and transit deep enough."""
        tds = self.transitobservationdetails_set.filter(site=site)
        observable = any([td.egress_observable for td in tds])
        return observable

    @property
    def details(self):
        return self.transitobservationdetails_set.all()

    @property
    def mag(self):
        return self.target.extra_fields["Mag (TESS)"]

    @property
    def depth(self):
        return self.target.extra_fields["Depth (mmag)"]

    class Meta:
        index_together = [
            ("target", "number"),
        ]

    def __str__(self):
        return f"Target {self.target}, transit number {self.number}, start, mid, end {self.start, self.mid, self.end}"


class TransitObservationDetails(models.Model):
    """Transit information at a given site."""

    transit = models.ForeignKey(Transit, on_delete=models.CASCADE)
    facility = models.TextField("Name of facility.")
    site = models.TextField("Name of site.")

    target_alt_start = models.FloatField("Elevation of target at start of transit")
    target_alt_mid = models.FloatField("Elevation of target at start of transit")
    target_alt_end = models.FloatField("Elevation of target at start of transit")
    sun_alt_mid = models.FloatField("Elevation of sun at mid-transit.")
    moon_alt_mid = models.FloatField("Elevation of moon at mid-transit.")
    moon_dist_mid = models.FloatField("Distance to moon at mid-transit.")

    visible = models.BooleanField("Whether transit is visible", null=True)
    observable = models.BooleanField(
        "Whether transit can be observed at this site", null=True
    )

    ingress_visible = models.BooleanField(
        "Whether transit ingress is visible", null=True
    )
    ingress_observable = models.BooleanField(
        "Whether transit ingress can be observed at this site", null=True
    )

    egress_visible = models.BooleanField("Whether transit egress is visible", null=True)
    egress_observable = models.BooleanField(
        "Whether transit egress can be observed at this site", null=True
    )

    class Meta:
        index_together = [
            ("transit", "facility", "site"),
        ]
