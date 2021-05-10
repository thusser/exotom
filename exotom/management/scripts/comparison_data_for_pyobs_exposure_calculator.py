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


def get_exposure_analysis_data():
    exposure_data = []

    for obs_record in ObservationRecord.objects.filter(
        status="COMPLETED",
        # created__gt=datetime.datetime(2021, 3, 29),  # , target__name__contains='2138'
    ):
        products = get_reduced_products(obs_record)

        dfs: [pd.DataFrame] = []
        for product in products[:3]:
            dfs.append(get_df(product))

        target_coord = SkyCoord(
            obs_record.target.ra * u.deg, obs_record.target.dec * u.deg
        )

        lce = LightCurvesExtractor(dfs, target_coord)
        lce.get_target_and_ref_stars_light_curves_df()

        target_id = lce.target_id
        matched_cats = lce.matched_image_catalogs_with_target

        target = obs_record.target
        try:
            exp_time = obs_record.parameters["exposure_time"]
            for cat in matched_cats:

                data = {
                    "name": target.name,
                    "exposure_time": exp_time,
                    "mag": target.targetextra_set.get(key="Mag (TESS)").float_value,
                    "peak": float(cat[cat["id"] == target_id]["peak"]),
                    "flux": float(cat[cat["id"] == target_id]["flux"]),
                    "fwhm": float(cat[cat["id"] == target_id]["fwhm"]),
                    "ellipticity": float(cat[cat["id"] == target_id]["ellipticity"]),
                }
                exposure_data.append(data)
        except:
            pass

        print(exposure_data[-1])

    print(exposure_data)


def get_df(product):
    resp = requests.get(
        product["url"].replace("download", "catalog"),
        headers=IAGFacility().archive_headers(),
    )
    product_data = resp.content
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


"""result
[{'name': 'TOI 1756.01', 'exposure_time': 12.800884405235431, 'mag': 12.0948, 'peak': 5860.05078125, 'flux': 35648.16180419922, 'fwhm': 3.159031318359815, 'ellipticity': 0.013655988759602387}, {'name': 'TOI 1756.01', 'exposure_time': 12.800884405235431, 'mag': 12.0948, 'peak': 5097.62255859375, 'flux': 36055.195861816406, 'fwhm': 3.3650778539286934, 'ellipticity': 0.041812768107939435}, {'name': 'TOI 1756.01', 'exposure_time': 12.800884405235431, 'mag': 12.0948, 'peak': 4854.89794921875, 'flux': 36361.660705566406, 'fwhm': 3.322696798464313, 'ellipticity': 0.019178230520171983}, {'name': 'TOI 1780.01', 'exposure_time': 13.749552287834481, 'mag': 12.212, 'peak': 13659.5380859375, 'flux': 52289.462463378906, 'fwhm': 2.8222172232335456, 'ellipticity': 0.036806304027289787}, {'name': 'TOI 1780.01', 'exposure_time': 13.749552287834481, 'mag': 12.212, 'peak': 11107.001953125, 'flux': 52289.866943359375, 'fwhm': 2.8883782493788206, 'ellipticity': 0.01197841624450613}, {'name': 'TOI 1780.01', 'exposure_time': 13.749552287834481, 'mag': 12.212, 'peak': 10526.5693359375, 'flux': 52384.885314941406, 'fwhm': 2.8906324078183467, 'ellipticity': 0.01805582462580313}, {'name': 'TOI 1841.01', 'exposure_time': 15.872693814490994, 'mag': 12.4474, 'peak': 5765.05322265625, 'flux': 52399.20385742188, 'fwhm': 3.6054609603259373, 'ellipticity': 0.03884266767789701}, {'name': 'TOI 1841.01', 'exposure_time': 15.872693814490994, 'mag': 12.4474, 'peak': 9236.3828125, 'flux': 52979.28662109375, 'fwhm': 3.234919410733661, 'ellipticity': 0.028438407518989295}, {'name': 'TOI 1841.01', 'exposure_time': 15.872693814490994, 'mag': 12.4474, 'peak': 8147.01806640625, 'flux': 53497.7919921875, 'fwhm': 3.201355037723156, 'ellipticity': 0.022237515293673682}, {'name': 'TOI 1852.01', 'exposure_time': 29.965216611401864, 'mag': 13.4891, 'peak': 6040.603515625, 'flux': 39826.07055664063, 'fwhm': 3.1230138708649315, 'ellipticity': 0.11479275405043865}, {'name': 'TOI 1852.01', 'exposure_time': 29.965216611401864, 'mag': 13.4891, 'peak': 5774.53173828125, 'flux': 39360.66870117188, 'fwhm': 3.189076643763761, 'ellipticity': 0.0744617333429678}, {'name': 'TOI 1852.01', 'exposure_time': 29.965216611401864, 'mag': 13.4891, 'peak': 6011.259765625, 'flux': 39369.8701171875, 'fwhm': 3.0773558129123564, 'ellipticity': 0.06543286881616761}, {'name': 'TOI 2046.01', 'exposure_time': 6.548567102236407, 'mag': 10.996, 'peak': 10756.49609375, 'flux': 83588.37664794923, 'fwhm': 3.588649766583972, 'ellipticity': 0.07234531641994013}, {'name': 'TOI 2046.01', 'exposure_time': 6.548567102236407, 'mag': 10.996, 'peak': 11307.18359375, 'flux': 85030.85394287111, 'fwhm': 3.385616275323962, 'ellipticity': 0.07351663438105904}, {'name': 'TOI 2046.01', 'exposure_time': 6.548567102236407, 'mag': 10.996, 'peak': 12112.2783203125, 'flux': 84670.9541015625, 'fwhm': 3.5044263817696524, 'ellipticity': 0.08255292948346915}, {'name': 'TOI 1151.01', 'exposure_time': 0.801319017395081, 'mag': 7.55216, 'peak': 27936.5546875, 'flux': 344896.63442993164, 'fwhm': 4.604632803632406, 'ellipticity': 0.05306827987037277}, {'name': 'TOI 1151.01', 'exposure_time': 0.801319017395081, 'mag': 7.55216, 'peak': 27044.763671875, 'flux': 343077.9365234375, 'fwhm': 4.487317267736374, 'ellipticity': 0.1269668388321652}, {'name': 'TOI 1151.01', 'exposure_time': 0.801319017395081, 'mag': 7.55216, 'peak': 34141.8125, 'flux': 343582.63052368164, 'fwhm': 4.030431499078561, 'ellipticity': 0.0766594782960297}, {'name': 'TOI 1342.01', 'exposure_time': 4.620529286447033, 'mag': 10.4243, 'peak': 12528.19140625, 'flux': 101870.85430908203, 'fwhm': 4.08668985902324, 'ellipticity': 0.06805409377575268}, {'name': 'TOI 1342.01', 'exposure_time': 4.620529286447033, 'mag': 10.4243, 'peak': 6541.51025390625, 'flux': 101672.5461730957, 'fwhm': 4.857084693973579, 'ellipticity': 0.04849088826382564}, {'name': 'TOI 1342.01', 'exposure_time': 4.620529286447033, 'mag': 10.4243, 'peak': 11173.1357421875, 'flux': 100311.44302368164, 'fwhm': 4.2529304286602745, 'ellipticity': 0.04195909375363982}, {'name': 'TOI 1810.01', 'exposure_time': 9.629461090307885, 'mag': 11.6281, 'peak': 10250.3720703125, 'flux': 67691.74621582031, 'fwhm': 3.2472995254640677, 'ellipticity': 0.1256289379926373}, {'name': 'TOI 1810.01', 'exposure_time': 9.629461090307885, 'mag': 11.6281, 'peak': 10813.6845703125, 'flux': 67606.26007080077, 'fwhm': 3.167825596812934, 'ellipticity': 0.14212513491037604}, {'name': 'TOI 1810.01', 'exposure_time': 9.629461090307885, 'mag': 11.6281, 'peak': 10613.19140625, 'flux': 67626.86004638673, 'fwhm': 3.0929555108823337, 'ellipticity': 0.1445118842790769}, {'name': 'TOI 1612.01', 'exposure_time': 3.682041164573349, 'mag': 10.0521, 'peak': 31580.55078125, 'flux': 118885.11193847655, 'fwhm': 3.0027766337237263, 'ellipticity': 0.12282731131341318}, {'name': 'TOI 1612.01', 'exposure_time': 3.682041164573349, 'mag': 10.0521, 'peak': 26793.474609375, 'flux': 119487.83947753905, 'fwhm': 2.9942153634302002, 'ellipticity': 0.09393152460247244}, {'name': 'TOI 1612.01', 'exposure_time': 3.682041164573349, 'mag': 10.0521, 'peak': 33082.81640625, 'flux': 118102.52926635742, 'fwhm': 3.1069952786772967, 'ellipticity': 0.08881463715792748}, {'name': 'TOI 2138.01', 'exposure_time': 16.862837947511405, 'mag': 12.5466, 'peak': 8277.7861328125, 'flux': 53224.24951171875, 'fwhm': 3.432073230221724, 'ellipticity': 0.05445583209846439}, {'name': 'TOI 2138.01', 'exposure_time': 16.862837947511405, 'mag': 12.5466, 'peak': 8318.755859375, 'flux': 52558.25329589844, 'fwhm': 3.3044641887599178, 'ellipticity': 0.034982538490659465}, {'name': 'TOI 2138.01', 'exposure_time': 16.862837947511405, 'mag': 12.5466, 'peak': 5560.11083984375, 'flux': 53357.24334716797, 'fwhm': 3.6928464195597375, 'ellipticity': 0.07936455285427213}, {'name': 'TOI 1511.01', 'exposure_time': 4.500084897447245, 'mag': 10.381, 'peak': 24643.001953125, 'flux': 123487.0622253418, 'fwhm': 3.160085878200562, 'ellipticity': 0.10868883110510108}, {'name': 'TOI 1511.01', 'exposure_time': 4.500084897447245, 'mag': 10.381, 'peak': 21246.662109375, 'flux': 124347.01921081544, 'fwhm': 3.1715070977299304, 'ellipticity': 0.09779872864586224}, {'name': 'TOI 1511.01', 'exposure_time': 4.500084897447245, 'mag': 10.381, 'peak': 16604.16796875, 'flux': 124407.25773620605, 'fwhm': 3.293670967908769, 'ellipticity': 0.08013742640663946}, {'name': 'TOI 1828.01', 'exposure_time': 7.1128375903433465, 'mag': 11.1315, 'peak': 14232.4375, 'flux': 82168.50559997559, 'fwhm': 3.5067435792005117, 'ellipticity': 0.004490582858853509}, {'name': 'TOI 1828.01', 'exposure_time': 7.1128375903433465, 'mag': 11.1315, 'peak': 12361.775390625, 'flux': 82732.96737670897, 'fwhm': 3.4916099254937576, 'ellipticity': 0.06107604440014092}, {'name': 'TOI 1828.01', 'exposure_time': 7.1128375903433465, 'mag': 11.1315, 'peak': 16061.986328125, 'flux': 82970.20831298827, 'fwhm': 3.2134009602017586, 'ellipticity': 0.027491822884893158}, {'name': 'TOI 1870.01', 'exposure_time': 19.776715536754246, 'mag': 12.8079, 'peak': 4675.53759765625, 'flux': 43496.898406982415, 'fwhm': 3.98976809798828, 'ellipticity': 0.14095854959321694}, {'name': 'TOI 1870.01', 'exposure_time': 19.776715536754246, 'mag': 12.8079, 'peak': 4227.6103515625, 'flux': 44978.06716918945, 'fwhm': 4.015330840912255, 'ellipticity': 0.1246398549367812}, {'name': 'TOI 1870.01', 'exposure_time': 19.776715536754246, 'mag': 12.8079, 'peak': 3971.196533203125, 'flux': 47215.077209472656, 'fwhm': 4.300826200023009, 'ellipticity': 0.17394228287774938}, {'name': 'TOI 1612.01', 'exposure_time': 3.682041164573349, 'mag': 10.0521, 'peak': 19001.62109375, 'flux': 105096.23203277588, 'fwhm': 3.497590969726526, 'ellipticity': 0.0635572757928623}, {'name': 'TOI 1612.01', 'exposure_time': 3.682041164573349, 'mag': 10.0521, 'peak': 17977.7421875, 'flux': 107114.67462158203, 'fwhm': 3.605815850165844, 'ellipticity': 0.06167374044390873}, {'name': 'TOI 1612.01', 'exposure_time': 3.682041164573349, 'mag': 10.0521, 'peak': 14662.4853515625, 'flux': 105858.6993637085, 'fwhm': 3.730275085281483, 'ellipticity': 0.0773680533699509}, {'name': 'TOI 1442.01', 'exposure_time': 16.324389252937046, 'mag': 12.4934, 'peak': 4076.89794921875, 'flux': 23260.82354736328, 'fwhm': 3.099040522759139, 'ellipticity': 0.01883543282434852}, {'name': 'TOI 1442.01', 'exposure_time': 16.324389252937046, 'mag': 12.4934, 'peak': 4219.01318359375, 'flux': 23139.92193603516, 'fwhm': 3.0993329802592813, 'ellipticity': 0.059331335565925285}, {'name': 'TOI 1442.01', 'exposure_time': 16.324389252937046, 'mag': 12.4934, 'peak': 3711.207275390625, 'flux': 23444.69592285156, 'fwhm': 3.181578743607958, 'ellipticity': 0.08763795263289509}, {'name': 'TOI 1516.01', 'exposure_time': 4.489118075261546, 'mag': 10.377, 'peak': 19801.919921875, 'flux': 109823.59338378906, 'fwhm': 3.3705875802232583, 'ellipticity': 0.07714490587858935}, {'name': 'TOI 1516.01', 'exposure_time': 4.489118075261546, 'mag': 10.377, 'peak': 16603.6875, 'flux': 110322.64981079102, 'fwhm': 3.574148854646208, 'ellipticity': 0.05327669635613663}, {'name': 'TOI 1516.01', 'exposure_time': 4.489118075261546, 'mag': 10.377, 'peak': 14599.2861328125, 'flux': 112649.70262908936, 'fwhm': 3.8190453613667343, 'ellipticity': 0.08127586423018962}]
"""
