import os
import pandas as pd

from django.core.files import File
from django.test import TestCase

from tom_dataproducts.models import DataProductGroup, DataProduct
from tom_observations.models import ObservationRecord

from exotom import transit_processor
from exotom.models import Target


class Test(TestCase):
    def setUp(self) -> None:
        self.data_dir = "exotom/test/test_transit_processor_data"
        self.file_paths = [
            os.path.join(self.data_dir, filename)
            for filename in os.listdir(self.data_dir)
        ]

        target1_dict = {
            "name": "test_TOI 1516.01",
            "type": "SIDEREAL",
            "ra": 340.08462499999996,
            "dec": 69.50373055555555,
        }
        # target1_extra_fields = {
        #     "Priority Proposal": False,  # <-- set to false!
        #     "Depth (mmag)": 19.323865,
        #     "Depth (mmag) err": 0.130853,
        #     "Duration (hours)": 2.230884,
        #     "Duration (hours) err": 0.021004,
        #     "Epoch (BJD)": 2458899.476842,
        #     "Epoch (BJD) err": 0.000252,
        #     "Mag (TESS)": 11.6281,
        #     "Period (days)": 1.327352,
        #     "Period (days) err": 2.1e-05,
        # }
        self.target1 = Target(**target1_dict)
        self.target1.save()  # extras=target1_extra_fields)

        self.obs_id = 9876
        self.transit_number = 1234
        self.obs_record = ObservationRecord.objects.create(
            target=self.target1,
            facility="IAGTransit",
            observation_id=self.obs_id,
            parameters={"transit": self.transit_number},
        )

        self.transit_dp_group = DataProductGroup(
            name=f"Target {self.target1.name}, transit #1234"
        )
        self.transit_dp_group.save()
        for file_path in self.file_paths:
            dp = DataProduct.objects.create(
                target=self.target1,
                observation_record=self.obs_record,
                data_product_type="image_photometry_catalog",
            )
            dp.group.add(self.transit_dp_group)
            with open(file_path) as f:
                dp.data.save(os.path.basename(file_path), File(f))
            dp.save()
            print(dp.data)

        self.transit_processor = transit_processor.TransitProcessor(
            self.transit_dp_group
        )

    def tearDown(self) -> None:
        print("Deleting all data product files")
        for dp in DataProduct.objects.all():
            os.remove(dp.data.path)

    def test_simple_processing(self):
        self.transit_processor.process_transit_dataproductgroup()

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

        self.assertEqual(len(photometry_cat_dps), len(self.file_paths))
        self.assertEqual(len(transit_all_light_curve_dps), 1)
        self.assertEqual(len(transit_best_light_curve_dps), 1)
        self.assertEqual(len(image_file_dps), 1)

        transit_light_curve_dp = transit_best_light_curve_dps[0]
        light_curves_df = pd.read_csv(transit_light_curve_dp.data.path)
        self.assertEqual(light_curves_df.shape[0], len(self.file_paths))
