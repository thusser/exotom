from django.test import TestCase
from unittest.mock import MagicMock, call
from tom_iag.iag import IAGFacility, IAGBaseForm

from exotom.models import Target, Transit, TransitObservationDetails

from astropy.time import Time
import datetime, pytz

from exotom.management.commands.submit_transit_observations import Command
from exotom.ofi.iagtransit import IAGTransitForm
from exotom.settings import PROPOSALS


class TestCommand(TestCase):
    def setUp(self) -> None:
        IAGFacility.submit_observation = MagicMock()

        # mock this methods since they make api calls to observation portal
        IAGBaseForm.proposal_choices = MagicMock(
            return_value=[
                (PROPOSALS["priority"], "High priority exoplanet obervations"),
                (PROPOSALS["low_priority"], "Low priority exoplanet obervations"),
            ]
        )

    def test_basic_observation_submission(self):

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

        test_nows = [
            Time("2021-01-18T12:00:00"),
            Time("2021-01-19T12:00:00"),
            Time("2021-01-22T12:00:00"),
        ]
        expected_call_args_lists = [
            [
                call(
                    {
                        "name": "HAT-P-36b #252",
                        "proposal": "exo",
                        "ipp_value": 1.05,
                        "operator": "SINGLE",
                        "observation_type": "NORMAL",
                        "requests": [
                            {
                                "configurations": [
                                    {
                                        "type": "REPEAT_EXPOSE",
                                        "repeat_duration": 10311.182400000016,
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
                                        "start": "2021-01-19T09:43:03.998",
                                        "end": "2021-01-19T12:46:55.180",
                                    }
                                ],
                                "location": {"telescope_class": "1m2"},
                            }
                        ],
                    }
                )
            ],
            [],
            [
                call(
                    {
                        "name": "HAT-P-36b #255",
                        "proposal": "exo",
                        "ipp_value": 1.05,
                        "operator": "SINGLE",
                        "observation_type": "NORMAL",
                        "requests": [
                            {
                                "configurations": [
                                    {
                                        "type": "REPEAT_EXPOSE",
                                        "repeat_duration": 10311.182399999996,
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
                                        "start": "2021-01-23T09:17:13.636",
                                        "end": "2021-01-23T12:21:04.819",
                                    }
                                ],
                                "location": {"telescope_class": "1m2"},
                            }
                        ],
                    }
                )
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
            IAGFacility.submit_observation.reset_mock()
            Time.now = MagicMock(return_value=test_now)
            cmd.handle()
            with self.subTest():
                self.assertEqual(
                    IAGFacility.submit_observation.call_args_list,
                    expected_call_args_list,
                    f"IAGFacility.submit_observation not called with expected args."
                    f" Called with {IAGFacility.submit_observation.call_args_list} instead of expected {expected_call_args_list}.",
                )

    def test_magnitude_and_transit_depth_check(self):
        # tests transit.observable check for mcdonald transit
        IAGFacility.submit_observation = MagicMock()

        test_now = Time("2021-01-18T12:00:00")
        Time.now = MagicMock(return_value=test_now)

        target1_dict = {
            "name": "OVERRIDDEN BELOW",
            "type": "SIDEREAL",
            "ra": 188.2662755371191,
            "dec": 44.9153325204756,
        }
        target1_extra_fields = {
            "Priority Proposal": True,
            "Depth (mmag)": "OVERRIDDEN BELOW",
            "Depth (mmag) err": 0.130853,
            "Duration (hours)": 2.230884,
            "Duration (hours) err": 0.021004,
            "Epoch (BJD)": 2458899.476842,
            "Epoch (BJD) err": 0.000252,
            "Mag (TESS)": "OVERRIDDEN BELOW",
            "Period (days)": 1.327352,
            "Period (days) err": 2.1e-05,
        }

        magnitudes = [8, 15, 25]  # limit for mcdonald is 20
        depths = [0.1, 1.2, 20]  # limit is 1 mmag
        magnitude_depth_pairs = [(mag, dep) for mag in magnitudes for dep in depths]
        expected_call_numbers = [0, 1, 1, 0, 1, 1, 0, 0, 0]

        cmd = Command()

        for (mag, depth), expected_call_number in zip(
            magnitude_depth_pairs, expected_call_numbers
        ):
            IAGFacility.submit_observation.reset_mock()
            Target.objects.all().delete()

            target1_dict["name"] = f"test_mag_{mag}_depth_{depth}_target"
            target1_extra_fields["Mag (TESS)"] = mag
            target1_extra_fields["Depth (mmag)"] = depth
            target1 = Target(**target1_dict)
            target1.save(extras=target1_extra_fields)

            cmd.handle()
            with self.subTest():
                number_of_calls = len(IAGFacility.submit_observation.call_args_list)
                self.assertEqual(
                    number_of_calls,
                    expected_call_number,
                    f"Call number {number_of_calls} is not equal to expected {expected_call_number}",
                )

    def test_low_priority_proposal_with_empty_proposa_extra_filled(self):
        Target.objects.all().delete()

        target1_dict = {
            "name": "HAT-P-36b",
            "type": "SIDEREAL",
            "ra": 188.2662755371191,
            "dec": 44.9153325204756,
        }
        target1_extra_fields = {
            #'Priority Proposal': False, # <-- not set/empty
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

        test_now = Time("2021-01-18T12:00:00")
        Time.now = MagicMock(return_value=test_now)

        expected_call_args_list = [
            call(
                {
                    "name": "HAT-P-36b #252",
                    "proposal": "exo_filler",
                    "ipp_value": 1.05,
                    "operator": "SINGLE",
                    "observation_type": "NORMAL",
                    "requests": [
                        {
                            "configurations": [
                                {
                                    "type": "REPEAT_EXPOSE",
                                    "repeat_duration": 10311.182400000016,
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
                                            "optical_elements": {"filter": "no_filter"},
                                        }
                                    ],
                                    "acquisition_config": {"mode": "ON"},
                                    "guiding_config": {"mode": "ON"},
                                    "constraints": {"max_airmass": 1.5},
                                }
                            ],
                            "windows": [
                                {
                                    "start": "2021-01-19T09:43:03.998",
                                    "end": "2021-01-19T12:46:55.180",
                                }
                            ],
                            "location": {"telescope_class": "1m2"},
                        }
                    ],
                }
            )
        ]

        # mock these methods since they make api calls to observation portal
        IAGBaseForm.proposal_choices = MagicMock(
            return_value=[
                ("exo", "Exoplanets (exo)"),
                ("exo_filler", "Low priority exoplanet obervations"),
            ]
        )

        cmd = Command()
        cmd.handle()

        call_arg_list = IAGFacility.submit_observation.call_args_list
        self.assertEqual(call_arg_list, expected_call_args_list)

    def test_low_priority_proposal_with_false_proposa_extra_filled(self):
        Target.objects.all().delete()

        target1_dict = {
            "name": "HAT-P-36b",
            "type": "SIDEREAL",
            "ra": 188.2662755371191,
            "dec": 44.9153325204756,
        }
        target1_extra_fields = {
            "Priority Proposal": False,  # <-- set to false!
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

        test_now = Time("2021-01-18T12:00:00")
        Time.now = MagicMock(return_value=test_now)

        expected_call_args_list = [
            call(
                {
                    "name": "HAT-P-36b #252",
                    "proposal": "exo_filler",
                    "ipp_value": 1.05,
                    "operator": "SINGLE",
                    "observation_type": "NORMAL",
                    "requests": [
                        {
                            "configurations": [
                                {
                                    "type": "REPEAT_EXPOSE",
                                    "repeat_duration": 10311.182400000016,
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
                                            "optical_elements": {"filter": "no_filter"},
                                        }
                                    ],
                                    "acquisition_config": {"mode": "ON"},
                                    "guiding_config": {"mode": "ON"},
                                    "constraints": {"max_airmass": 1.5},
                                }
                            ],
                            "windows": [
                                {
                                    "start": "2021-01-19T09:43:03.998",
                                    "end": "2021-01-19T12:46:55.180",
                                }
                            ],
                            "location": {"telescope_class": "1m2"},
                        }
                    ],
                }
            )
        ]

        cmd = Command()
        cmd.handle()

        call_arg_list = IAGFacility.submit_observation.call_args_list
        self.assertEqual(call_arg_list, expected_call_args_list)
