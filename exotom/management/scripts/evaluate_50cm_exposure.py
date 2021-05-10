import datetime
import io

import requests
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.time import Time
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

from tom_iag.iag import IAGFacility
import pandas as pd
import numpy as np

from exotom import settings
from exotom.photometry import LightCurvesExtractor


def evaluate_50cm_exposure_times():
    peaks = {}

    for obs_record in ObservationRecord.objects.filter(
        status="COMPLETED",
        created__gt=datetime.datetime(2021, 3, 29),  # , target__name__contains='2138'
    ):
        products = get_reduced_products(obs_record)

        dfs: [pd.DataFrame] = []
        for product in products[::5]:
            dfs.append(get_df(product))

        target_coord = SkyCoord(
            obs_record.target.ra * u.deg, obs_record.target.dec * u.deg
        )

        lce = LightCurvesExtractor(dfs, target_coord)
        lce.get_target_and_ref_stars_light_curves_df()

        target_id = lce.target_id
        matched_cats = lce.matched_image_catalogs_with_target

        peakss = []
        peakxs = []
        peakys = []
        for cat in matched_cats:
            # print(cat)
            peakss.append(float(cat[cat["id"] == target_id]["peak"]))
            peakxs.append(int(cat[cat["id"] == target_id]["xpeak"]))
            peakys.append(int(cat[cat["id"] == target_id]["ypeak"]))

        target = obs_record.target
        peaks[target.name] = {
            "peak": np.mean(np.array(peakss)),
            "peaks": peakss,
            "peak_std": np.std(np.array(peakss)),
            "peakxs": peakxs,
            "peakys": peakys,
            "mag": target.targetextra_set.get(key="Mag (TESS)").float_value,
        }

        print(len(dfs))
    print(peaks)


def get_df(product):
    product_data = requests.get(
        product["url"].replace("download", "catalog"),
        headers=IAGFacility().archive_headers(),
    ).content
    # print(product_data)
    time_str = product["created"]
    df = pd.read_csv(io.StringIO(product_data.decode("utf-8")))
    df["time"] = float(Time(time_str).jd)
    return df


def get_reduced_products(obs_record):
    all_products = IAGFacility().data_products(obs_record.observation_id)
    all_products = list(
        filter(lambda prod: prod["imagetype"] == "object", all_products)
    )
    all_products_reduced = list(
        filter(
            lambda prod: prod["rlevel"] == 1,
            all_products,
        )
    )
    return all_products_reduced


if __name__ == "__main__":
    evaluate_50cm_exposure_times()
