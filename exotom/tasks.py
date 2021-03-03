import io, json, os, time, requests
import pandas as pd
from astropy.time import Time

from django.core.files.base import ContentFile
from django.core.management import call_command
from tom_dataproducts.models import DataProduct, DataProductGroup, ReducedDatum
from tom_dataproducts.utils import create_image_dataproduct
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


@app.task
def process_new_reduced_dataproducts():
    for observation_record in ObservationRecord.objects.all():
        try:
            analyse_transit_observation(observation_record)
        except Exception as e:
            print(f"Tranit analysis failed becase of '{e}'")


def analyse_transit_observation(observation_record):
    if observation_record.status == "COMPLETED":
        (
            reduced_products,
            reduction_pipeline_finished,
        ) = get_reduced_data_products(observation_record)

        if not reduction_pipeline_finished:
            raise Exception("Reduction pipeline not finished.")

        # print(type(json.loads(observation_record.parameters)))
        # print(json.loads(observation_record.parameters))
        # transit_number = json.loads(observation_record.parameters)["transit"]
        transit_dp_group = DataProductGroup(
            name=f"Target {observation_record.target.name}, transit #"  # {transit_number}"
        )
        transit_dp_group.save()
        for ip, product in enumerate(reduced_products):
            if ip % 100 == 0:
                print(f"creating data product {ip}/{len(reduced_products)}: {product}")

            dp, created = DataProduct.objects.get_or_create(
                product_id=product["id"],
                target=observation_record.target,
                observation_record=observation_record,
                data_product_type="photometry_catalog",
                # group=transit_dp_group,
            )
            dp.group.add(transit_dp_group)

            if created:

                for attempts in range(3):
                    try:
                        product_data = requests.get(
                            product["url"].replace("download", "catalog"),
                            headers=IAGFacility()._archive_headers(),
                        ).content
                        header: str = requests.get(
                            product["url"].replace("download", "headers"),
                            headers=IAGFacility()._archive_headers(),
                        ).content

                        break
                    except Exception as e:
                        print(
                            f"Data request to {product['url']} failed due to '{e}'. {2 - attempts} left..."
                        )
                        time.sleep(0.5)

                df = get_catalog_dataframe_from_catalog_and_headers(
                    header, product_data
                )
                dfile = ContentFile(df.to_csv())
                dp.data.save(product["filename"].replace(".fits.gz", ".csv"), dfile)
                dp.save()
                # if AUTO_THUMBNAILS:
                # create_image_dataproduct(dp)
            #     dp.get_preview()

        data_processor = TransitProcessor()
        data = data_processor.process_data_group(transit_dp_group)

        reduced_datums = [
            ReducedDatum(
                target=observation_record.target,
                # data_product=dp,
                # data_type=dp.data_product_type,
                timestamp=datum[0],
                value=datum[1],
            )
            for datum in data
        ]
        ReducedDatum.objects.bulk_create(reduced_datums)

        for dp in transit_dp_group.dataproduct_set.all():
            os.remove(dp.data.path)
            dp.delete()
        transit_dp_group.delete()


def get_catalog_dataframe_from_catalog_and_headers(header, product_data):
    time_str = list(
        filter(
            lambda res: "DATE-OBS" in res.values(),
            json.loads(header)["results"],
        )
    )[0]["value"]
    df = pd.read_csv(io.StringIO(product_data.decode("utf-8")))
    df["time"] = float(Time(time_str, format="fits").jd)
    return df


CALIBRATED_REDUCTION_LEVEL = 1


def get_reduced_data_products(observation_record) -> (list, bool):
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

    return all_products_reduced, reduction_pipeline_finished
