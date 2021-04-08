from django.test import TestCase
from unittest.mock import MagicMock, call
from tom_iag.iag import IAGFacility, IAGBaseForm
from tom_observations.models import ObservationRecord

from exotom.models import Target

from astropy.time import Time

from exotom.management.commands.submit_transit_contact_observations import Command


class TestCommand(TestCase):
    def setUp(self) -> None:
        IAGFacility.submit_observation = MagicMock(return_value=[1212])
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
                                        "repeat_duration": 2310.987624000003,
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
                                                "exposure_time": 3.6723439653643895,
                                                "mode": "sbig8300_1x1",
                                                "optical_elements": {
                                                    "filter": "no_filter"
                                                },
                                            }
                                        ],
                                        "acquisition_config": {"mode": "ON"},
                                        "guiding_config": {"mode": "ON"},
                                        "constraints": {"max_airmass": 2.0},
                                    }
                                ],
                                "windows": [
                                    {
                                        "start": "2021-01-19T09:38:36.837",
                                        "end": "2021-01-19T10:29:07.825",
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
                                        "repeat_duration": 2310.9876239999985,
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
                                                "exposure_time": 3.6723439653643895,
                                                "mode": "sbig8300_1x1",
                                                "optical_elements": {
                                                    "filter": "no_filter"
                                                },
                                            }
                                        ],
                                        "acquisition_config": {"mode": "ON"},
                                        "guiding_config": {"mode": "ON"},
                                        "constraints": {"max_airmass": 2.0},
                                    }
                                ],
                                "windows": [
                                    {
                                        "start": "2021-01-19T11:52:28.019",
                                        "end": "2021-01-19T12:42:59.007",
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
            ObservationRecord.objects.all().delete()

            Time.now = MagicMock(return_value=test_now)
            cmd.handle()
            with self.subTest():
                call_arg_list = IAGFacility.submit_observation.call_args_list
                # print(call_arg_list)
                self.assertEqual(
                    call_arg_list,
                    expected_call_args_list,
                    f"IAGFacility.submit_observation not called with expected args.\n"
                    f" Called with {call_arg_list}\n instead of expected\n {expected_call_args_list}.",
                )

                n_expected_obs_records = len(expected_call_args_list)
                obs_records = ObservationRecord.objects.all()
                self.assertEqual(
                    len(obs_records),
                    n_expected_obs_records,
                    f"obs_records does not have length {n_expected_obs_records} (obs_records = {obs_records}).",
                )

                if n_expected_obs_records > 0:
                    obs_record = ObservationRecord.objects.all()[0]
                    self.assertEqual(obs_record.target, self.target1)
