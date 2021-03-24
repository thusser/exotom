import datetime

import pytz
from astroplan import EclipsingSystem, Observer
from astropy.coordinates import SkyCoord, EarthLocation
from astropy.time import Time, TimeDelta
import astropy.units as u
import numpy as np
from tom_observations.facility import get_service_classes

from exotom.models import Transit, Target, TransitObservationDetails
from exotom.ofi.iagtransit import IAGTransitFacility
from exotom.settings import SITES


def calculate_transits_during_next_n_days(
    target: Target, n_days: int = 10, start_time: datetime.datetime = None
):

    if start_time is not None:
        now = Time(start_time)
    else:
        now = Time.now()

    # remove all future transits
    Transit.objects.filter(
        target=target, start__gt=now.datetime.astimezone(pytz.utc)
    ).delete()

    # got epoch and period?
    if (
        "Epoch (BJD)" not in target.extra_fields
        or target.extra_fields["Epoch (BJD)"] is None
        or "Period (days)" not in target.extra_fields
        or target.extra_fields["Period (days)"] is None
        or "Duration (hours)" not in target.extra_fields
        or target.extra_fields["Duration (hours)"] is None
    ):
        return

    # create observers
    observers = {
        code: Observer(
            latitude=site["latitude"] * u.deg,
            longitude=site["longitude"] * u.deg,
            elevation=site["elevation"] * u.m,
        )
        for code, site in IAGTransitFacility.SITES.items()
    }

    # get coordinates
    target_coords = SkyCoord(target.ra * u.deg, target.dec * u.deg)

    # parse epoch
    # transit barycentric correction only wrt to earth center, not specific observatory location
    earth_center = EarthLocation.from_geocentric(0, 0, 0, unit=u.m)
    epoch_barycenter = Time(
        target.extra_fields["Epoch (BJD)"],
        format="jd",
        scale="tdb",
        location=earth_center,
    )
    period = target.extra_fields["Period (days)"] * u.day
    duration = target.extra_fields["Duration (hours)"] * u.hour

    # create system
    system = EclipsingSystem(
        primary_eclipse_time=epoch_barycenter, orbital_period=period, duration=duration
    )

    # find eclipses within next n days
    obstime = now
    while True:
        # find next eclipse
        eclipse_barycenter = system.next_primary_eclipse_time(obstime)[0]
        transit_number = int(
            np.round((eclipse_barycenter.jd - epoch_barycenter.jd) / period.value)
        )

        # apply barycentric correction
        ltt = eclipse_barycenter.light_travel_time(
            target_coords, kind="barycentric", location=earth_center
        )
        eclipse = eclipse_barycenter - ltt

        # too far?
        if eclipse > now + TimeDelta(n_days * u.day):
            break

        # get start and end times
        start = eclipse - duration / 2
        end = eclipse + duration / 2

        # should not have started yet
        if start > now:
            # create transit
            transit = Transit()
            transit.target = target
            transit.number = transit_number
            transit.start = start.datetime.astimezone(pytz.utc)
            transit.mid = eclipse.datetime.astimezone(pytz.utc)
            transit.end = end.datetime.astimezone(pytz.utc)
            transit.save()

            # loop facilities
            for site, observer in observers.items():
                # create transit details
                details = create_transit_details(
                    transit, observer, target_coords, start, eclipse, end, site
                )

                # save
                details.save()

        # next one
        obstime = eclipse + TimeDelta(30 * u.minute)


def create_transit_details(transit: Transit, observer, coords, start, mid, end, site):
    # margin
    margin = 25 * u.min

    # get position of sun and moon
    sun = {
        "start": observer.sun_altaz(start - margin),
        "mid": observer.sun_altaz(mid),
        "end": observer.sun_altaz(end + margin),
    }
    moon = observer.moon_altaz(mid)

    # position of target
    target = {
        "start": observer.altaz(start - margin, coords),
        "mid": observer.altaz(mid, coords),
        "end": observer.altaz(end + margin, coords),
    }

    # coords to altaz at mid-transit
    alt_az_start = observer.altaz(start, coords)
    alt_az_mid = observer.altaz(mid, coords)
    alt_az_end = observer.altaz(end, coords)

    # create new TransitSite and fill it
    details = TransitObservationDetails()
    details.target_alt_start = target["start"].alt.degree
    details.target_alt_mid = target["mid"].alt.degree
    details.target_alt_end = target["end"].alt.degree
    details.sun_alt_mid = sun["mid"].alt.degree
    details.moon_alt_mid = moon.alt.degree
    details.moon_dist_mid = alt_az_mid.separation(moon).degree

    moon_dist_start = alt_az_start.separation(moon).degree
    moon_dist_end = alt_az_end.separation(moon).degree

    transit_observation_constraints_at_site = SITES[site][
        "transitObservationConstraints"
    ]

    details.visible = (
        details.target_alt_start > 30
        and details.target_alt_mid > 30
        and details.target_alt_end > 30
        and sun["start"].alt.degree < -12
        and details.sun_alt_mid < -12
        and sun["end"].alt.degree < -12
        and details.moon_dist_mid > 30
    )
    details.observable = (
        details.visible
        and transit.mag <= transit_observation_constraints_at_site["maxMagnitude"]
        and transit.depth
        >= transit_observation_constraints_at_site["minTransitDepthInMmag"]
    )

    # visibility/observability for ingress/egress of transit only
    details.ingress_visible = (
        details.target_alt_start > 30
        and sun["start"].alt.degree < -12
        and moon_dist_start > 30
    )
    details.ingress_observable = (
        details.ingress_visible
        and transit.mag <= transit_observation_constraints_at_site["maxMagnitude"]
        and transit.depth
        >= transit_observation_constraints_at_site["minTransitDepthInMmag"]
    )

    details.egress_visible = (
        details.target_alt_end > 30
        and sun["end"].alt.degree < -12
        and moon_dist_end > 30
    )
    details.egress_observable = (
        details.egress_visible
        and transit.mag <= transit_observation_constraints_at_site["maxMagnitude"]
        and transit.depth
        >= transit_observation_constraints_at_site["minTransitDepthInMmag"]
    )

    # fill details
    details.transit = transit
    details.facility = "IAGTransit"
    details.site = site

    # return it
    return details
