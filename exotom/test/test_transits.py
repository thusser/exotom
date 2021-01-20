from django.test import TestCase
from unittest.mock import MagicMock

from exotom.transits import calculate_transits_during_next_n_days

from exotom.models import Target, Transit, TransitObservationDetails
from astropy.time import Time
import datetime, pytz


class Test(TestCase):

    def setUp(self) -> None:
        self.test_now = Time('2021-01-18T12:00:00')
        Time.now = MagicMock(return_value=self.test_now)

        target1_dict = {'name': 'HAT-P-36b', 'type': 'SIDEREAL', 'ra': 188.2662755371191, 'dec': 44.9153325204756}
        target1_extra_fields = {'Depth (mmag)': 19.323865, 'Depth (mmag) err': 0.130853,
                                'Duration (hours)': 2.230884, 'Duration (hours) err': 0.021004,
                                'Epoch (BJD)': 2458899.476842, 'Epoch (BJD) err': 0.000252,
                                'Mag (TESS)': 11.6281, 'Period (days)': 1.327352,
                                'Period (days) err': 2.1e-05}
        self.target1 = Target(**target1_dict)
        self.target1.save(extras=target1_extra_fields)

    def test_calculate_transits_during_next_n_days(self):

        calculate_n_days_ahead = 5
        expect_n_transits = 4
        first_transit_number = 252
        expected_transit_numbers = list(range(first_transit_number, first_transit_number + expect_n_transits))

        expected_transits = [{'start': datetime.datetime(2021, 1, 19, 10, 8, 3, 997995, tzinfo=pytz.utc),
                              'mid': datetime.datetime(2021, 1, 19, 11, 14, 59, 589195, tzinfo=pytz.utc),
                              'end': datetime.datetime(2021, 1, 19, 12, 21, 55, 180395, tzinfo=pytz.utc), },
                             {'start': datetime.datetime(2021, 1, 20, 17, 59, 27, 210795, tzinfo=pytz.utc),
                              'mid': datetime.datetime(2021, 1, 20, 19, 6, 22, 801995, tzinfo=pytz.utc),
                              'end': datetime.datetime(2021, 1, 20, 20, 13, 18, 393195, tzinfo=pytz.utc), },
                             {'start': datetime.datetime(2021, 1, 22, 1, 50, 50, 423595, tzinfo=pytz.utc),
                              'mid': datetime.datetime(2021, 1, 22, 2, 57, 46, 14795, tzinfo=pytz.utc),
                              'end': datetime.datetime(2021, 1, 22, 4, 4, 41, 605995, tzinfo=pytz.utc), },
                             {'start': datetime.datetime(2021, 1, 23, 9, 42, 13, 636395, tzinfo=pytz.utc),
                              'mid': datetime.datetime(2021, 1, 23, 10, 49, 9, 227595, tzinfo=pytz.utc),
                              'end': datetime.datetime(2021, 1, 23, 11, 56, 4, 818795, tzinfo=pytz.utc), },
                             ]

        expected_details = [{'site': 'Sutherland', 'observable': False},
                            {'site': 'McDonald', 'observable': True},
                            {'site': 'Göttingen', 'observable': False},
                            {'site': 'Sutherland', 'observable': False},
                            {'site': 'McDonald', 'observable': False},
                            {'site': 'Göttingen', 'observable': False},
                            {'site': 'Sutherland', 'observable': False},
                            {'site': 'McDonald', 'observable': False},
                            {'site': 'Göttingen', 'observable': True},
                            {'site': 'Sutherland', 'observable': False},
                            {'site': 'McDonald', 'observable': True},
                            {'site': 'Göttingen', 'observable': False},]

        transits_before = Transit.objects.all()
        self.assertTrue(len(transits_before) == 0)

        calculate_transits_during_next_n_days(self.target1, n_days=calculate_n_days_ahead)
        transits_after = Transit.objects.all()
        self.assertTrue(len(transits_after) == expect_n_transits,
                        f"No of transits is not {expect_n_transits} but {len(transits_after)}")

        transit_numbers = [transit.number for transit in transits_after]
        self.assertTrue(transit_numbers == expected_transit_numbers,
                        f"Transit numbers are not {expected_transit_numbers} but {transit_numbers}")

        for transit, exp_transit in zip(transits_after, expected_transits):
            with self.subTest():
                self.assertEqual(transit.start, exp_transit['start'])
                self.assertEqual(transit.mid, exp_transit['mid'])
                self.assertEqual(transit.end, exp_transit['end'])

        transit_observation_details = TransitObservationDetails.objects.all()
        for transit_observation_detail, exp_details in zip(transit_observation_details, expected_details):
            self.assertEqual(transit_observation_detail.site, exp_details['site'])
            self.assertEqual(transit_observation_detail.observable, exp_details['observable'])

