import logging
from django.db import models
from tom_targets.models import Target

log = logging.getLogger(__name__)


class Transit(models.Model):
    """A single transit."""
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    number = models.IntegerField('Transit number')

    start = models.DateTimeField('Time the transit starts')
    mid = models.DateTimeField('Time of mid-transit')
    end = models.DateTimeField('Time the transit ends')

    def uncertainty(self):
        return (self.target.extra_fields['Epoch (BJD) err']
                + self.number * self.target.extra_fields['Period (days) err']) * 1440

    @property
    def facilities(self):
        return list(set([(td.facility, td.site) for td in self.transitobservationdetails_set.all() if td.observable]))

    def observable(self, facility):
        return any([td.observable for td in self.transitobservationdetails_set.filter(facility=facility)])

    def observable_at_site(self, site):
        tds = self.transitobservationdetails_set.filter(site=site)
        observable = any([td.observable for td in tds])
        return observable
    @property
    def details(self):
        return self.transitobservationdetails_set.all()

    @property
    def mag(self):
        return self.target.extra_fields['Mag (TESS)']

    @property
    def depth(self):
        return self.target.extra_fields['Depth (mmag)']

    class Meta:
        index_together = [
            ('target', 'number'),
        ]

    def __str__(self):
        return f"Target {self.target}, transit number {self.number}, start, mid, end {self.start, self.mid, self.end}"


class TransitObservationDetails(models.Model):
    """Transit information at a given site."""
    transit = models.ForeignKey(Transit, on_delete=models.CASCADE)
    facility = models.TextField('Name of facility.')
    site = models.TextField('Name of site.')

    target_alt_start = models.FloatField('Elevation of target at start of transit')
    target_alt_mid = models.FloatField('Elevation of target at start of transit')
    target_alt_end = models.FloatField('Elevation of target at start of transit')
    sun_alt_mid = models.FloatField('Elevation of sun at mid-transit.')
    moon_alt_mid = models.FloatField('Elevation of moon at mid-transit.')
    moon_dist_mid = models.FloatField('Distance to moon at mid-transit.')

    observable = models.BooleanField('Whether transit is observable')

    class Meta:
        index_together = [
            ('transit', 'facility', 'site'),
        ]
