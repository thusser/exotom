import glob
import os
import time

import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u


from astropy.io import fits
from astropy.table import Table
from astropy.time import Time
from tom_dataproducts.models import DataProductGroup

from exotom.photometry import LightCurveExtractor

MAX_SEPARATION_TO_CATALOG_IN_DEG = 5 / 3600


class TransitProcessor:
    def process_data_group(self, data_product_group: DataProductGroup):

        dps = data_product_group.dataproduct_set.all()
        print(f"Transit processing {len(dps)} data products: {dps}")

        data_directory = os.path.dirname(dps[0].data.path)
        target_coord = SkyCoord(dps[0].target.ra * u.deg, dps[0].target.dec * u.deg)

        image_catalogs, one_image = self.load_data_from_directory_of_csv_catalogs(
            data_directory
        )
        lce = LightCurveExtractor(
            image_catalogs, target_coord, one_image_for_plot=one_image
        )
        (
            target_relative_light_curve,
            cmp_light_curves,
        ) = lce.get_best_relative_light_curve()

        print(target_relative_light_curve)
        print(cmp_light_curves)
        tuples = []
        for target_rel_lc_pt, cmp_lc_series in zip(
            target_relative_light_curve.iteritems(), cmp_light_curves.iterrows()
        ):

            timestamp = str(Time(target_rel_lc_pt[0], format="jd").iso)

            value_dict = {"target_rel_mag": target_rel_lc_pt[1]}
            for cmp_star_index, cmp_star_mag in cmp_lc_series[1].iteritems():
                value_dict[f"cmp_star_{cmp_star_index}_mag"] = cmp_star_mag

            tuples.append((timestamp, value_dict))
        return tuples

    @staticmethod
    def load_data_from_directory_of_csv_catalogs(data_directory, verbose=False):
        print("Starting data load")
        # load all catalogs
        start = time.time()
        image_catalogs = []
        files = sorted(glob.glob(os.path.join(data_directory, "*.csv")))
        # print(files)
        for i, filename in enumerate(sorted(files), 1):
            # load data
            if verbose or i % 50 == 0:
                print("(%d/%d) Loading %s..." % (i, len(files), filename))

            cat = pd.read_csv(filename)
            image_catalogs.append(cat)
        print("Load took %.2fs" % (time.time() - start,))
        return image_catalogs, None  # , one_image

    @staticmethod
    def load_data_from_directory_of_compressed_fits(data_directory, verbose=False):
        print("Starting data load")
        # load all catalogs
        start = time.time()
        image_catalogs = []
        files = sorted(glob.glob(os.path.join(data_directory, "*.fits.gz")))
        for i, filename in enumerate(sorted(files), 1):
            # load data
            if verbose or i % 50 == 0:
                print("(%d/%d) Loading %s..." % (i, len(files), filename))

            if i == 100:
                one_image = fits.open(filename)[0].data

            hdr = fits.getheader(filename, "SCI")
            cat = Table(fits.getdata(filename, "CAT")).to_pandas()

            # add date-obs
            cat["time"] = float(Time(hdr["DATE-OBS"]).jd)

            # append
            image_catalogs.append(cat)
        print("Load took %.2fs" % (time.time() - start,))
        return image_catalogs, one_image
