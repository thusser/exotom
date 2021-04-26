import datetime

import pytz
from astroplan import EclipsingSystem, Observer
from astropy.coordinates import SkyCoord, EarthLocation
from astropy.time import Time, TimeDelta
import astropy.units as u
import numpy as np

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
                details = create_transit_details(transit, observer, target_coords, site)

                # save
                details.save()

        # next one
        obstime = eclipse + TimeDelta(30 * u.minute)


def create_transit_details(transit: Transit, observer, coords, site):
    start, mid, end = transit.start, transit.mid, transit.end
    observing_start, observing_end = transit.get_observing_window()

    (
        ingress_observing_start,
        ingress_observing_end,
    ) = transit.get_ingress_observing_window()
    egress_observing_start, egress_observing_end = transit.get_egress_observing_window()

    times = [
        start,
        mid,
        end,
        observing_start,
        observing_end,
        ingress_observing_start,
        ingress_observing_end,
        egress_observing_start,
        egress_observing_end,
    ]

    sun_positions = {time: observer.sun_altaz(time) for time in times}
    target_positions = {time: observer.altaz(time, coords) for time in times}
    moon_positions = {time: observer.moon_altaz(mid) for time in times}

    # create new TransitObservationDetails object and fill it
    details = TransitObservationDetails()
    details.target_alt_mid = target_positions[mid].alt.degree
    details.target_alt_start = target_positions[start].alt.degree
    details.target_alt_end = target_positions[end].alt.degree
    details.sun_alt_mid = sun_positions[mid].alt.degree
    details.moon_alt_mid = moon_positions[mid].alt.degree
    details.moon_dist_mid = target_positions[mid].separation(moon_positions[mid]).degree

    moon_dist_start = target_positions[start].separation(moon_positions[start]).degree
    moon_dist_end = target_positions[end].separation(moon_positions[end]).degree

    transit_observation_constraints_at_site = SITES[site][
        "transitObservationConstraints"
    ]

    details.visible = (
        details.target_alt_start > 30
        and details.target_alt_mid > 30
        and details.target_alt_end > 30
        and sun_positions[start].alt.degree < -12
        and details.sun_alt_mid < -12
        and sun_positions[end].alt.degree < -12
        and moon_positions[start].alt.degree > 30
        and details.moon_dist_mid > 30
        and moon_positions[end].alt.degree > 30
    )
    details.observable = (
        # same as visible but with margins = baseline observation time and transit timing errors
        (
            target_positions[observing_start].alt.degree > 30
            and details.target_alt_mid > 30
            and target_positions[observing_end].alt.degree > 30
            and sun_positions[observing_start].alt.degree < -12
            and details.sun_alt_mid < -12
            and sun_positions[observing_end].alt.degree < -12
            and moon_positions[observing_start].alt.degree > 30
            and details.moon_dist_mid > 30
            and moon_positions[observing_end].alt.degree > 30
        )
        # telescope constraints
        and transit.mag <= transit_observation_constraints_at_site["maxMagnitude"]
        and transit.depth
        >= transit_observation_constraints_at_site["minTransitDepthInMmag"]
    )

    # visibility/observability for ingress/egress of transit only
    details.ingress_visible = (
        details.target_alt_start > 30
        and sun_positions[start].alt.degree < -12
        and moon_dist_start > 30
    )
    details.ingress_observable = (
        details.ingress_visible
        # check margins = baseline observation time and transit timing errors
        and target_positions[ingress_observing_start].alt.degree > 30
        and target_positions[ingress_observing_end].alt.degree > 30
        # telescope constraints
        and transit.mag <= transit_observation_constraints_at_site["maxMagnitude"]
        and transit.depth
        >= transit_observation_constraints_at_site["minTransitDepthInMmag"]
    )

    details.egress_visible = (
        details.target_alt_end
        and sun_positions[end].alt.degree < -12
        and moon_dist_end > 30
    )
    details.egress_observable = (
        details.egress_visible
        and target_positions[egress_observing_start].alt.degree > 30
        and target_positions[egress_observing_end].alt.degree > 30
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
