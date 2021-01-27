from django.test import TestCase
from unittest.mock import MagicMock, call
from tom_iag.iag import IAGFacility, IAGBaseForm

from exotom.models import Target, Transit, TransitObservationDetails

from astropy.time import Time
import datetime, pytz

from exotom.management.commands.submit_transit_contact_observations import Command
from exotom.ofi.iagtransit import IAGTransitForm
from exotom.settings import PROPOSALS


class TestCommand(TestCase):
    def setUp(self) -> None:
        IAGFacility.submit_observation = MagicMock()
        pass

    def test_basic_transit_contact_observation_submission(self):

        target1_dict = {
            "name": "HAT-P-36b",
            "type": "SIDEREAL",
            "ra": 188.2662755371191,
            "dec": 44.9153325204756,
        }
        target1_extra_fields = {
            "Priority Proposal": True,
            "Depth (mmag)": 19.323865,
            "Depth (mmag) err": 0.130853,
            "Duration (hours)": 2.230884,
            "Duration (hours) err": 0.021004,
            "Epoch (BJD)": 2458899.476842,
            "Epoch (BJD) err": 0.000252,
            "Mag (TESS)": 11.6281,
            "Period (days)": 1.327352,
            "Period (days) err": 2.1e-05,
        }
        self.target1 = Target(**target1_dict)
        self.target1.save(extras=target1_extra_fields)

        test_nows = [Time("2021-01-18T12:00:00")]

        expected_call_args_lists = [
            [
                call(
                    {
                        "name": "HAT-P-36b #252 INGRESS",
                        "proposal": "exo",
                        "ipp_value": 0.5,
                        "operator": "SINGLE",
                        "observation_type": "NORMAL",
                        "requests": [
                            {
                                "configurations": [
                                    {
                                        "type": "REPEAT_EXPOSE",
                                        "repeat_duration": 1679.9999999999916,
                                        "instrument_type": "1M2 SBIG8300",
                                        "target": {
                                            "name": "HAT-P-36b",
                                            "type": "ICRS",
                                            "ra": 188.2662755371191,
                                            "dec": 44.9153325204756,
                                            "proper_motion_ra": None,
                                            "proper_motion_dec": None,
                                            "epoch": None,
                                        },
                                        "instrument_configs": [
                                            {
                                                "exposure_count": 1,
                                                "exposure_time": 9.629461090307885,
                                                "mode": "sbig8300_1x1",
                                                "optical_elements": {
                                                    "filter": "no_filter"
                                                },
                                            }
                                        ],
                                        "acquisition_config": {"mode": "ON"},
                                        "guiding_config": {"mode": "ON"},
                                        "constraints": {"max_airmass": 1.5},
                                    }
                                ],
                                "windows": [
                                    {
                                        "start": "2021-01-19T09:48:03.998",
                                        "end": "2021-01-19T10:28:03.998",
                                    }
                                ],
                                "location": {"telescope_class": "1m2"},
                            }
                        ],
                    }
                ),
                call(
                    {
                        "name": "HAT-P-36b #252 EGRESS",
                        "proposal": "exo",
                        "ipp_value": 0.5,
                        "operator": "SINGLE",
                        "observation_type": "NORMAL",
                        "requests": [
                            {
                                "configurations": [
                                    {
                                        "type": "REPEAT_EXPOSE",
                                        "repeat_duration": 1679.9999999999916,
                                        "instrument_type": "1M2 SBIG8300",
                                        "target": {
                                            "name": "HAT-P-36b",
                                            "type": "ICRS",
                                            "ra": 188.2662755371191,
                                            "dec": 44.9153325204756,
                                            "proper_motion_ra": None,
                                            "proper_motion_dec": None,
                                            "epoch": None,
                                        },
                                        "instrument_configs": [
                                            {
                                                "exposure_count": 1,
                                                "exposure_time": 9.629461090307885,
                                                "mode": "sbig8300_1x1",
                                                "optical_elements": {
                                                    "filter": "no_filter"
                                                },
                                            }
                                        ],
                                        "acquisition_config": {"mode": "ON"},
                                        "guiding_config": {"mode": "ON"},
                                        "constraints": {"max_airmass": 1.5},
                                    }
                                ],
                                "windows": [
                                    {
                                        "start": "2021-01-19T12:01:55.180",
                                        "end": "2021-01-19T12:41:55.180",
                                    }
                                ],
                                "location": {"telescope_class": "1m2"},
                            }
                        ],
                    }
                ),
            ],
        ]
        IAGBaseForm.proposal_choices = MagicMock(
            return_value=[
                ("exo", "Exoplanets (exo)"),
                ("exo_filler", "Low priority exoplanet obervations"),
            ]
        )

        cmd = Command()

        for test_now, expected_call_args_list in zip(
            test_nows, expected_call_args_lists
        ):
            # IAGFacility.submit_observation.reset_mock()
            Time.now = MagicMock(return_value=test_now)
            cmd.handle()
            with self.subTest():
                call_arg_list = IAGFacility.submit_observation.call_args_list
                # print(call_arg_list)
                self.assertEqual(
                    call_arg_list,
                    expected_call_args_list,
                    f"IAGFacility.submit_observation not called with expected args."
                    f" Called with {call_arg_list} instead of expected {expected_call_args_list}.",
                )
