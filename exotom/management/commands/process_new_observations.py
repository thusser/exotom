import io, os, time, traceback, requests
import pandas as pd
from astropy.time import Time

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from tom_dataproducts.models import DataProduct, DataProductGroup
from tom_observations.models import ObservationRecord

from tom_iag.iag import IAGFacility
from exotom.transit_processor import TransitProcessor
from exotom.management.commands.update_observation_status import (
    update_observation_status_command,
)


class Command(BaseCommand):
    help = "Submit all transits that can be observed in the following night to telescope scheduler."

    def handle(self, *args, **options):
        process_new_observations_command()


def process_new_observations_command():
    update_observation_status_command()

    for observation_record in ObservationRecord.objects.all():
        try:
            downloader = TransitObservationDownloader(observation_record)
            downloader.attempt_analyse_transit_observation()
        except Exception as e:
            print(f"Transit analysis failed because of '{e}'")


class TransitObservationDownloader:
    """Downloads photometry catalogs of transit observations and creates transit_all_lightcurves DataProduct"""

    CALIBRATED_REDUCTION_LEVEL_INT = 1

    def __init__(self, observation_record):
        self.observation_record = observation_record

    def attempt_analyse_transit_observation(self):
        if (
            self.observation_record.status == "COMPLETED"
            and not self.transit_all_lightcurves_dataproduct_exists()
        ):
            self.lock_observation_record_for_analysis()
            try:
                self.analyse_observation_record()
            except Exception as e:
                print(
                    f"Analysis of ObservationRecord {self.observation_record} failed due to '{e}'. Traceback:"
                )
                traceback.print_exc()
            finally:
                self.unlock_observation_record_from_analysis()

    def lock_observation_record_for_analysis(self):
        self.observation_record.status = "ANALYSING"
        self.observation_record.save()

    def unlock_observation_record_from_analysis(self):
        self.observation_record.status = "COMPLETED"
        self.observation_record.save()

    def analyse_observation_record(self):
        reduced_products = self.get_reduced_data_products_and_check_pipeline_finished()
        transit_dataproduct_group = self.create_transit_dataproduct_group()
        try:
            for i_product, product in enumerate(reduced_products):
                if i_product % 100 == 0:
                    print(
                        f"creating data product {i_product}/{len(reduced_products)}: {product}"
                    )

                dp, created = self.get_or_create_image_photometry_catalog_dataproduct(
                    self.observation_record, product, transit_dataproduct_group
                )

                if created:
                    self.save_dataproduct_file(dp, product)
            data_processor = TransitProcessor(transit_dataproduct_group)
            data_processor.process()
        except Exception as e:
            raise e
        finally:
            self.clean_up_image_photometry_catalog_dataproducts(
                transit_dataproduct_group
            )

    def transit_all_lightcurves_dataproduct_exists(self):
        dps_for_obs_record = DataProduct.objects.filter(
            observation_record=self.observation_record
        )
        for dp in dps_for_obs_record:
            if dp.data_product_type == "transit_all_light_curves":
                return True
        return False

    def get_reduced_data_products_and_check_pipeline_finished(
        self,
    ) -> (list, bool):
        all_products = IAGFacility().data_products(
            self.observation_record.observation_id
        )
        all_products = list(
            filter(lambda prod: prod["imagetype"] == "object", all_products)
        )
        all_products_reduced = list(
            filter(
                lambda prod: prod["rlevel"] == self.CALIBRATED_REDUCTION_LEVEL_INT,
                all_products,
            )
        )

        reduction_pipeline_finished: bool = True
        if not len(all_products_reduced) * 2 >= len(all_products):
            print(
                f"Not all images have been calibrated yet "
                f"({len(all_products_reduced)} reduced images and {len(all_products)} total object images)."
            )
            reduction_pipeline_finished = False

        if not reduction_pipeline_finished:
            raise Exception("Reduction pipeline not finished.")

        return all_products_reduced

    def create_transit_dataproduct_group(self):
        transit_dp_group_name = self.get_transit_name(self.observation_record)

        transit_dp_group = DataProductGroup(name=transit_dp_group_name)
        transit_dp_group.save()
        return transit_dp_group

    def get_or_create_image_photometry_catalog_dataproduct(
        self, observation_record, product, transit_dp_group
    ):
        dp, created = DataProduct.objects.get_or_create(
            product_id=product["id"],
            target=observation_record.target,
            observation_record=observation_record,
            data_product_type="image_photometry_catalog",
        )
        dp.group.add(transit_dp_group)
        return dp, created

    def get_transit_name(self, observation_record):
        try:
            transit_dp_group_name = observation_record.parameters["name"]
        except:
            try:
                transit_number = observation_record.parameters["transit"]
            except:
                transit_number = "unknown"
            transit_dp_group_name = (
                f"Target {observation_record.target.name}, transit #{transit_number}"
            )

        return transit_dp_group_name

    def save_dataproduct_file(self, dp, product):
        product_data, time_datetime = self.attempt_image_catalog_download(
            product, n_attempts=3
        )
        df = self.get_catalog_dataframe_from_catalog_and_time(
            product_data, time_datetime
        )
        dfile = ContentFile(df.to_csv())
        dp.data.save(product["filename"].replace(".fits.gz", ".csv"), dfile)
        dp.save()

    def attempt_image_catalog_download(self, product, n_attempts):
        for attempts in range(n_attempts):
            try:
                product_data = requests.get(
                    product["url"].replace("download", "catalog"),
                    headers=IAGFacility().archive_headers(),
                ).content
                time_str = product["created"]
                break
            except Exception as e:
                print(
                    f"Data request to {product['url']} failed due to '{e}'. {2 - attempts} attempts left..."
                )
                time.sleep(0.5)
        else:
            raise Exception(
                f"Couldn't download data from {product['url']} after {n_attempts} due to '{e}'."
            )

        return product_data, time_str

    def get_catalog_dataframe_from_catalog_and_time(self, product_data, time_datetime):
        df = pd.read_csv(io.StringIO(product_data.decode("utf-8")))
        df["time"] = float(Time(time_datetime).jd)
        return df

    def clean_up_image_photometry_catalog_dataproducts(self, transit_dp_group):
        for dp in transit_dp_group.dataproduct_set.all():
            os.remove(dp.data.path)
            dp.delete()
        transit_dp_group.delete()
