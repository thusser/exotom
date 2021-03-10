import io, os, time, requests, traceback
import pandas as pd
from astropy.time import Time

from django.core.files.base import ContentFile
from django.core.management import call_command
from tom_dataproducts.models import DataProduct, DataProductGroup
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

from exotom.management.commands.submit_transit_observations import submit_all_transits
from exotom.management.commands.submit_transit_contact_observations import (
    submit_all_transit_contacts,
)
from exotom.transit_processor import TransitProcessor
from exotom.transits import calculate_transits_during_next_n_days
from exotom.celery import app
from tom_iag.iag import IAGFacility


@app.task
def submit_observations():
    # calculate transits for next 24 hours
    for target in Target.objects.all():
        calculate_transits_during_next_n_days(target, 1)

    # submit observable transits
    submit_all_transits()

    # submit just ingres/egress
    submit_all_transit_contacts()


@app.task
def update_observation_status():
    for target in Target.objects.all():
        call_command("updatestatus", target_id=target.id)

    # delete
    for obs_record in ObservationRecord.objects.all():
        if obs_record.status in ["CANCELED", "WINDOW_EXPIRED"]:
            obs_record.delete()


@app.task
def process_new_observations():
    update_observation_status()

    for observation_record in ObservationRecord.objects.all():
        try:
            attempt_analyse_transit_observation(observation_record)
        except Exception as e:
            print(f"Transit analysis failed because of '{e}'")


def attempt_analyse_transit_observation(observation_record):
    if (
        observation_record.status == "COMPLETED"
        and not transit_light_curve_dataproduct_exists_for_observation_record(
            observation_record
        )
    ):
        # "lock" observation_record, so no second analysis is started.
        observation_record.status = "ANALYSING"
        observation_record.save()

        try:
            analyse_observation_record(observation_record)
        except Exception as e:
            print(
                f"Analysis of ObservationRecord {observation_record} failed due to '{e}'. Traceback:"
            )
            traceback.print_exc()
        finally:
            # unlock observation_record
            observation_record.status = "COMPLETED"
            observation_record.save()


def analyse_observation_record(observation_record):
    reduced_products = get_reduced_data_products_and_check_pipeline_finished(
        observation_record
    )
    transit_dataproduct_group = create_transit_dataproduct_group(observation_record)
    try:
        for i_product, product in enumerate(reduced_products):
            if i_product % 100 == 0:
                print(
                    f"creating data product {i_product}/{len(reduced_products)}: {product}"
                )

            dp, created = get_or_create_image_photometry_catalog_dataproduct(
                observation_record, product, transit_dataproduct_group
            )

            if created:
                save_dataproduct_file(dp, product)
        data_processor = TransitProcessor()
        data_processor.process_transit_dataproductgroup(transit_dataproduct_group)
    except Exception as e:
        raise e
    finally:
        clean_up_image_photometry_catalog_dataproducts(transit_dataproduct_group)


def transit_light_curve_dataproduct_exists_for_observation_record(observation_record):
    dps_for_obs_record = DataProduct.objects.filter(
        observation_record=observation_record
    )
    for dp in dps_for_obs_record:
        if dp.data_product_type == "transit_light_curve":
            return True
    return False


def get_reduced_data_products_and_check_pipeline_finished(
    observation_record,
) -> (list, bool):
    all_products = IAGFacility().data_products(observation_record.observation_id)
    all_products = list(
        filter(lambda prod: prod["imagetype"] == "object", all_products)
    )
    all_products_reduced = list(
        filter(
            lambda prod: prod["rlevel"] == CALIBRATED_REDUCTION_LEVEL,
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


def create_transit_dataproduct_group(observation_record):
    transit_number = observation_record.parameters["transit"]
    transit_dp_group = DataProductGroup(
        name=f"Target {observation_record.target.name}, transit #{transit_number}"
    )
    transit_dp_group.save()
    return transit_dp_group


def get_or_create_image_photometry_catalog_dataproduct(
    observation_record, product, transit_dp_group
):
    dp, created = DataProduct.objects.get_or_create(
        product_id=product["id"],
        target=observation_record.target,
        observation_record=observation_record,
        data_product_type="image_photometry_catalog",
    )
    dp.group.add(transit_dp_group)
    return dp, created


def save_dataproduct_file(dp, product):
    product_data, time_datetime = attempt_image_catalog_download(product, n_attempts=3)
    df = get_catalog_dataframe_from_catalog_and_time(product_data, time_datetime)
    dfile = ContentFile(df.to_csv())
    dp.data.save(product["filename"].replace(".fits.gz", ".csv"), dfile)
    dp.save()


def attempt_image_catalog_download(product, n_attempts):
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


def get_catalog_dataframe_from_catalog_and_time(product_data, time_datetime):
    df = pd.read_csv(io.StringIO(product_data.decode("utf-8")))
    df["time"] = float(Time(time_datetime).jd)
    return df


def clean_up_image_photometry_catalog_dataproducts(transit_dp_group):
    for dp in transit_dp_group.dataproduct_set.all():
        os.remove(dp.data.path)
        dp.delete()
    transit_dp_group.delete()


CALIBRATED_REDUCTION_LEVEL = 1
