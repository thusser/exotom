from urllib.parse import urljoin

from astropy.coordinates import SkyCoord
import astropy.units as u
from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from tom_targets.models import Target
from django import forms
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from django.core.cache import cache
from bs4 import BeautifulSoup
import requests


broker_url = "http://var2.astro.cz/ETD/index.php"


class ETDForm(GenericQueryForm):
    max_mag = forms.FloatField(required=True)
    min_depth = forms.FloatField(required=True)


class ETD(GenericBroker):
    name = "ETD"
    form = ETDForm

    @staticmethod
    def _scrape_etd():
        # download
        session = requests.session()
        html = session.get(broker_url)
        soup = BeautifulSoup(html.text, "html.parser")

        # list of objects
        objects = []

        # find all transiters
        for link in soup.find_all("p", attrs={"class": "listStarItem"}):
            # get URL and name
            url = urljoin("http://var2.astro.cz/ETD/", link.a["href"])
            name = link.a.string
            print(url, name)

            # download that page
            html2 = session.get(url)
            soup2 = BeautifulSoup(html2.text, "html.parser")

    @classmethod
    def fetch_alerts(clazz, parameters):
        cached_tois = cache.get("etd_tois")

        if not cached_tois:
            # download data
            TOI_df = pd.read_csv(broker_url, delimiter="|", index_col=False)

            # filter
            TOI_df = TOI_df[TOI_df["TESS Mag"] < parameters["max_mag"]]
            TOI_df = TOI_df[TOI_df["Depth (mmag)"] > parameters["min_depth"]]

            # to dicts
            cached_tois = [alert.to_dict() for _, alert in TOI_df.iterrows()]
            cache.set("etd_tois", cached_tois)

        print(cached_tois)
        return iter(cached_tois)

    @classmethod
    def to_generic_alert(clazz, alert):
        # RA/Dec to decimal
        coords = SkyCoord(alert["RA"], alert["Dec"], unit=(u.hour, u.deg), frame="icrs")

        import pprint

        pprint.pprint(alert)

        # create generic alert
        return ExoFOPTESSAlert(
            timestamp=alert["Date TOI Alerted (UTC)"],
            url="https://exofop.ipac.caltech.edu/tess/target.php?id=%d"
            % alert["TIC ID"],
            id=alert["TIC ID"],
            name=str(alert["TOI"]),
            ra=coords.ra.deg,
            dec=coords.dec.deg,
            mag=alert["TESS Mag"],
            score=alert["ACWG"],
            epoch=alert["Epoch (BJD)"],
            epoch_err=alert["Epoch (BJD) err"],
            period=alert["Period (days)"],
            period_err=alert["Period (days) err"],
            duration=alert["Duration (hours)"],
            duration_err=alert["Duration (hours) err"],
            depth=alert["Depth (mmag)"],
            depth_err=alert["Depth (mmag) err"],
        )


@dataclass
class ExoFOPTESSAlert(GenericAlert):
    """
    dataclass representing an alert in order to display it in the UI.
    """

    epoch: float
    epoch_err: float
    period: float
    period_err: float
    duration: float
    duration_err: float
    depth: float
    depth_err: float

    def to_target(self):
        """
        Returns a Target instance for an object defined by an alert.

        :returns: representation of object for an alert
        :rtype: `Target`
        """
        return (
            Target(name=self.name, type="SIDEREAL", ra=self.ra, dec=self.dec),
            {
                "Priority": self.score,
                "Mag (TESS)": self.mag,
                "Epoch (BJD)": self.epoch,
                "Epoch (BJD) err": self.epoch_err,
                "Period (days)": self.period,
                "Period (days) err": self.period_err,
                "Duration (hours)": self.duration,
                "Duration (hours) err": self.duration_err,
                "Depth (mmag)": self.depth,
                "Depth (mmag) err": self.depth_err,
            },
            [],
        )
