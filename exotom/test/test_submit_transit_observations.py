from django.test import TestCase
from unittest.mock import MagicMock, call
from tom_iag.iag import IAGFacility, IAGBaseForm
from tom_observations.models import ObservationRecord

from exotom.models import Target

from astropy.time import Time

from exotom.management.commands.submit_transit_observations import submit_all_transits
from exotom.settings import PROPOSALS


class TestCommand(TestCase):
    def setUp(self) -> None:
        IAGFacility.submit_observation = MagicMock(return_value=[1212])

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
                                        "repeat_duration": 10026.676212000004,
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
                                        "start": "2021-01-19T09:41:14.584",
                                        "end": "2021-01-19T12:40:21.260",
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
                                        "repeat_duration": 10037.550435999996,
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
                                        "start": "2021-01-23T09:15:01.294",
                                        "end": "2021-01-23T12:14:18.844",
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
                ("exofiller", "Low priority exoplanet obervations"),
            ]
        )

        for test_now, expected_call_args_list in zip(
            test_nows, expected_call_args_lists
        ):
            IAGFacility.submit_observation.reset_mock()
            ObservationRecord.objects.all().delete()

            Time.now = MagicMock(return_value=test_now)
            submit_all_transits()
            with self.subTest():
                self.assertEqual(
                    IAGFacility.submit_observation.call_args_list,
                    expected_call_args_list,
                    f"IAGFacility.submit_observation not called with expected args."
                    f" Called with \n{IAGFacility.submit_observation.call_args_list}\n instead of expected\n {expected_call_args_list}.",
                )

                n_expected_obs_records = 1 if expected_call_args_list != [] else 0
                obs_records = ObservationRecord.objects.all()
                self.assertEqual(
                    len(obs_records),
                    n_expected_obs_records,
                    f"obs_records does not have length {n_expected_obs_records} (obs_records = {obs_records}).",
                )

                if n_expected_obs_records != 0:
                    obs_record = ObservationRecord.objects.all()[0]
                    self.assertEqual(obs_record.target, self.target1)

    def test_magnitude_and_transit_depth_check(self):
        # tests transit.observable check for mcdonald transit
        IAGFacility.submit_observation = MagicMock(return_value=[1212])

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

        for (mag, depth), expected_call_number in zip(
            magnitude_depth_pairs, expected_call_numbers
        ):
            IAGFacility.submit_observation.reset_mock()
            Target.objects.all().delete()
            ObservationRecord.objects.all().delete()

            target1_dict["name"] = f"test_mag_{mag}_depth_{depth}_target"
            target1_extra_fields["Mag (TESS)"] = mag
            target1_extra_fields["Depth (mmag)"] = depth
            target1 = Target(**target1_dict)
            target1.save(extras=target1_extra_fields)

            submit_all_transits()
            with self.subTest():
                number_of_calls = len(IAGFacility.submit_observation.call_args_list)
                self.assertEqual(
                    number_of_calls,
                    expected_call_number,
                    f"Call number {number_of_calls} is not equal to expected {expected_call_number}",
                )

                obs_records = ObservationRecord.objects.all()
                self.assertEqual(
                    len(obs_records),
                    expected_call_number,
                    f"obs_records does not have length {expected_call_number} (obs_records = {obs_records}).",
                )

                if expected_call_number != 0:
                    obs_record = ObservationRecord.objects.all()[0]
                    self.assertEqual(obs_record.target, target1)

    def test_low_priority_proposal_with_empty_proposal_extra_filled(self):
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
                    "proposal": "exofiller",
                    "ipp_value": 1.05,
                    "operator": "SINGLE",
                    "observation_type": "NORMAL",
                    "requests": [
                        {
                            "configurations": [
                                {
                                    "type": "REPEAT_EXPOSE",
                                    "repeat_duration": 10026.676212000004,
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
                                            "optical_elements": {"filter": "no_filter"},
                                        }
                                    ],
                                    "acquisition_config": {"mode": "ON"},
                                    "guiding_config": {"mode": "ON"},
                                    "constraints": {"max_airmass": 2.0},
                                }
                            ],
                            "windows": [
                                {
                                    "start": "2021-01-19T09:41:14.584",
                                    "end": "2021-01-19T12:40:21.260",
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
                ("exofiller", "Low priority exoplanet obervations"),
            ]
        )

        submit_all_transits()

        call_arg_list = IAGFacility.submit_observation.call_args_list
        self.assertEqual(call_arg_list, expected_call_args_list)

    def test_low_priority_proposal_with_false_proposal_extra_filled(self):
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
                    "proposal": "exofiller",
                    "ipp_value": 1.05,
                    "operator": "SINGLE",
                    "observation_type": "NORMAL",
                    "requests": [
                        {
                            "configurations": [
                                {
                                    "type": "REPEAT_EXPOSE",
                                    "repeat_duration": 10026.676212000004,
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
                                            "optical_elements": {"filter": "no_filter"},
                                        }
                                    ],
                                    "acquisition_config": {"mode": "ON"},
                                    "guiding_config": {"mode": "ON"},
                                    "constraints": {"max_airmass": 2.0},
                                }
                            ],
                            "windows": [
                                {
                                    "start": "2021-01-19T09:41:14.584",
                                    "end": "2021-01-19T12:40:21.260",
                                }
                            ],
                            "location": {"telescope_class": "1m2"},
                        }
                    ],
                }
            )
        ]

        submit_all_transits()

        call_arg_list = IAGFacility.submit_observation.call_args_list
        self.assertEqual(call_arg_list, expected_call_args_list)
