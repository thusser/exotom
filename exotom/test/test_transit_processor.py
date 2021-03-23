import os
from unittest.mock import MagicMock

import pandas as pd
from astropy.time import Time

from django.core.files import File
from django.test import TestCase

from tom_dataproducts.models import DataProductGroup, DataProduct
from tom_observations.models import ObservationRecord

from exotom import transit_processor
from exotom.models import Target, Transit
from exotom.transits import calculate_transits_during_next_n_days


class Test(TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        print("Deleting all data product files")
        for dp in DataProduct.objects.all():
            os.remove(dp.data.path)

    def test_simple_processing_without_fit(self):
        # no transit object is created, so no fit is done

        # given
        data_dir = "exotom/test/test_transit_processor_data_short"
        file_paths = [
            os.path.join(data_dir, filename) for filename in os.listdir(data_dir)
        ]

        target1_dict = {
            "name": "test_TOI 1516.01",
            "type": "SIDEREAL",
            "ra": 340.08462499999996,
            "dec": 69.50373055555555,
        }

        target1 = Target(**target1_dict)
        target1.save()  # extras=target1_extra_fields)

        obs_id = 9876
        transit_number = 1234
        obs_record = ObservationRecord.objects.create(
            target=target1,
            facility="IAGTransit",
            observation_id=obs_id,
            parameters={"transit": transit_number},
        )

        transit_dp_group = DataProductGroup(
            name=f"Target {target1.name}, transit #1234"
        )
        transit_dp_group.save()
        for file_path in file_paths:
            dp = DataProduct.objects.create(
                target=target1,
                observation_record=obs_record,
                data_product_type="image_photometry_catalog",
            )
            dp.group.add(transit_dp_group)
            with open(file_path) as f:
                dp.data.save(os.path.basename(file_path), File(f))
            dp.save()
            print(dp.data)

        transit_processorr = transit_processor.TransitProcessor(transit_dp_group)

        transit_processorr.process()

        photometry_cat_dps = DataProduct.objects.filter(
            data_product_type="image_photometry_catalog"
        )
        transit_all_light_curve_dps = DataProduct.objects.filter(
            data_product_type="transit_all_light_curves"
        )
        transit_best_light_curve_dps = DataProduct.objects.filter(
            data_product_type="transit_best_light_curves"
        )
        image_file_dps = DataProduct.objects.filter(data_product_type="image_file")

        self.assertEqual(len(photometry_cat_dps), len(file_paths))
        self.assertEqual(len(transit_all_light_curve_dps), 1)
        self.assertEqual(len(transit_best_light_curve_dps), 1)
        self.assertEqual(len(image_file_dps), 1)

        transit_light_curve_dp = transit_best_light_curve_dps[0]
        light_curves_df = pd.read_csv(transit_light_curve_dp.data.path)
        self.assertEqual(light_curves_df.shape[0], len(file_paths))

    def test_long_processing_with_fit(self):
        # given
        data_dir = "exotom/test/test_transit_processor_data_long_with_fit"
        file_paths = [
            os.path.join(data_dir, filename) for filename in os.listdir(data_dir)
        ]

        target1_dict = {
            "name": "test_TOI 1809.01",
            "type": "SIDEREAL",
            "ra": 183.3660,
            "dec": 23.0557,
        }
        target1_extra_fields = {
            "Priority Proposal": False,
            "Mag (TESS)": 11.6281,
            "Epoch (BJD)": 2458902.718492,
            "Duration (hours)": 3.588807,
            "Period (days)": 4.617208,
            "Depth (mmag)": 12.207647,
            "Planet Radius (R_Earth)": 12.041519,
            "Stellar Radius (R_Sun)": 1.1136,
            "Stellar Distance (pc)": 321.084,
        }
        target1 = Target(**target1_dict)
        target1.save(extras=target1_extra_fields)

        # create transit object by running calculate_transits_during_next_n_days
        test_now = Time("2021-02-21T15:00:00")
        Time.now = MagicMock(return_value=test_now)
        calculate_transits_during_next_n_days(target1, 1)
        # make sure transit #79 was created
        transit1 = Transit.objects.get(target=target1, number=79)

        obs_id = 9876
        transit_number = 1234
        obs_record = ObservationRecord.objects.create(
            target=target1,
            facility="IAGTransit",
            observation_id=obs_id,
            parameters={"transit": transit_number, "transit_id": transit1.id},
        )

        transit_dp_group = DataProductGroup(name=f"Target {target1.name}, transit #79")
        transit_dp_group.save()
        for file_path in file_paths:
            dp = DataProduct.objects.create(
                target=target1,
                observation_record=obs_record,
                data_product_type="image_photometry_catalog",
            )
            dp.group.add(transit_dp_group)
            with open(file_path) as f:
                dp.data.save(os.path.basename(file_path), File(f))
            dp.save()
            print(dp.data)

        transit_processorr = transit_processor.TransitProcessor(transit_dp_group)

        transit_processorr.process()

        photometry_cat_dps = DataProduct.objects.filter(
            data_product_type="image_photometry_catalog"
        )
        transit_all_light_curve_dps = DataProduct.objects.filter(
            data_product_type="transit_all_light_curves"
        )
        transit_best_light_curve_dps = DataProduct.objects.filter(
            data_product_type="transit_best_light_curves"
        )
        image_file_dps = DataProduct.objects.filter(data_product_type="image_file")

        self.assertEqual(len(photometry_cat_dps), len(file_paths))
        self.assertEqual(len(transit_all_light_curve_dps), 1)
        self.assertEqual(len(transit_best_light_curve_dps), 1)
        self.assertEqual(len(image_file_dps), 1)

        transit_light_curve_dp = transit_best_light_curve_dps[0]
        light_curves_df = pd.read_csv(transit_light_curve_dp.data.path)
        self.assertEqual(light_curves_df.shape[0], len(file_paths))
