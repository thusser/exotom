import pytz
from astroplan import EclipsingSystem, Observer
from astropy.coordinates import SkyCoord
from astropy.time import Time, TimeDelta
import astropy.units as u
import numpy as np
from tom_observations.facility import get_service_classes

from exotom.models import Transit, Target, TransitObservationDetails
from exotom.ofi.iagtransit import IAGTransitFacility


def calculate_transits_during_next_n_days(target: Target, n_days: int = 10):
    # init
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
    coords = SkyCoord(target.ra * u.deg, target.dec * u.deg)

    # parse epoch
    epoch = Time(target.extra_fields["Epoch (BJD)"], format="jd", scale="tdb")
    period = target.extra_fields["Period (days)"] * u.day
    duration = target.extra_fields["Duration (hours)"] * u.hour

    # create system
    system = EclipsingSystem(
        primary_eclipse_time=epoch.utc, orbital_period=period, duration=duration
    )

    # find eclipses within next 10 days
    obstime = now
    while True:
        # find next eclipse
        eclipse = system.next_primary_eclipse_time(obstime)[0]
        number = int(np.round((eclipse.jd - epoch.jd) / period.value))

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
            transit.number = number
            transit.start = start.datetime.astimezone(pytz.utc)
            transit.mid = eclipse.datetime.astimezone(pytz.utc)
            transit.end = end.datetime.astimezone(pytz.utc)
            transit.save()

            # loop facilities
            for site, observer in observers.items():
                # create transit details
                details = create_transit_details(observer, coords, start, eclipse, end)

                # fill details
                details.transit = transit
                details.facility = "IAGTransit"
                details.site = site

                # save
                details.save()

        # next one
        obstime = eclipse + TimeDelta(5 * u.minute)


def create_transit_details(observer, coords, start, mid, end):
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
    alt_az = observer.altaz(mid, coords)

    # create new TransitSite and fill it
    details = TransitObservationDetails()
    details.target_alt_start = target["start"].alt.degree
    details.target_alt_mid = target["mid"].alt.degree
    details.target_alt_end = target["end"].alt.degree
    details.sun_alt_mid = sun["mid"].alt.degree
    details.moon_alt_mid = moon.alt.degree
    details.moon_dist_mid = alt_az.separation(moon).degree

    # decide, whether it's observable
    details.observable = (
        details.target_alt_start > 30
        and details.target_alt_mid > 30
        and details.target_alt_end > 30
        and sun["start"].alt.degree < -12
        and details.sun_alt_mid < -12
        and sun["end"].alt.degree < -12
        and details.moon_dist_mid > 30
    )

    # return it
    return details
