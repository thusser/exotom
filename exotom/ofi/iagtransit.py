from astropy.time import Time
from crispy_forms.layout import Div, Layout
from django import forms
from dateutil.parser import parse
from tom_targets.models import Target, TargetExtra
from django.conf import settings
import astropy.units as u

from tom_iag.iag import (
    IAG50ImagingObservationForm,
    IAGFacility,
    MonetSouthImagingObservationForm,
    MonetNorthImagingObservationForm,
    IAGImagingObservationForm,
    IAGBaseObservationForm,
    IAGBaseForm,
)
from exotom.models import Transit

from local_settings import PROPOSALS

# Determine settings for this module.
try:
    SETTINGS = settings.FACILITIES["IAGTransit"]
except (AttributeError, KeyError):
    SETTINGS = {
        "instruments": {
            "McDonald": "1M2 SBIG8300",
            "Sutherland": "1M2 FLI230",
            "Göttingen": "0M5 SBIG6303E",
        },
        "proposal": "exo",
        "max_airmass": 1.5,
    }


class IAGTransitForm(IAGImagingObservationForm):
    name = forms.CharField(max_length=200)

    def __init__(self, *args, **kwargs):
        IAGImagingObservationForm.__init__(self, *args, **kwargs)

        # transit field
        transits = []
        for c in self.transit_choices():
            if c[0] == int(self.initial["transit"]):
                transits.append(c)
        self.fields["transit"] = forms.ChoiceField(choices=transits)

    def layout(self):
        return Div(
            Div(
                Div(
                    "transit",
                    css_class="col",
                ),
                css_class="row",
            ),
            Div(
                Div(
                    "instrument_type",
                    css_class="col",
                ),
                css_class="row",
            ),
            Div(
                Div("readout_mode", css_class="col"),
                Div("filter", css_class="col"),
                css_class="form-row",
            ),
            Div(
                Div("exposure_time", css_class="col"),
                Div("ipp_value", css_class="col"),
                css_class="form-row",
            ),
        )

    def transit_choices(self):
        return sorted(
            [
                (t.number, "#%d: %s" % (t.number, t.start.strftime("%Y/%m/%d %H:%M")))
                for t in Transit.objects.filter(start__gt=Time.now().isot)
                if t.visible(self.initial["facility"])
            ],
            key=lambda x: x[1],
        )

    def clean_start(self):
        start = self.cleaned_data["start"]
        return parse(start).isoformat()

    def clean_end(self):
        end = self.cleaned_data["end"]
        return parse(end).isoformat()

    def _build_acquisition_config(self):
        acquisition_config = {"mode": "ON"}

        return acquisition_config

    def _build_guiding_config(self):
        guiding_config = {"mode": "ON"}

        return guiding_config

    def _build_configuration(self, duration):
        return {
            "type": "REPEAT_EXPOSE",
            "repeat_duration": (duration - 12 * u.min).sec,
            "instrument_type": self.cleaned_data["instrument_type"],
            "target": self._build_target_fields(),
            "instrument_configs": self._build_instrument_config(),
            "acquisition_config": self._build_acquisition_config(),
            "guiding_config": self._build_guiding_config(),
            "constraints": {"max_airmass": self.cleaned_data["max_airmass"]},
        }

    def _build_window(self):
        # get target and transit
        target = Target.objects.get(pk=self.cleaned_data["target_id"])
        transit = Transit.objects.get(
            target=target, number=self.cleaned_data["transit"]
        )

        # calculate start, end and duration
        start = Time(transit.start_earliest()) - 15 * u.min
        end = Time(transit.end_latest()) + 15 * u.min
        duration = end - start

        # return it
        return {"start": start.isot, "end": end.isot}, duration

    def _build_instrument_config(self):
        return [
            {
                "exposure_count": 1,
                "exposure_time": self.cleaned_data["exposure_time"],
                "mode": self.cleaned_data["readout_mode"],
                "optical_elements": {"filter": self.cleaned_data["filter"]},
            }
        ]

    def observation_payload(self):
        # get target and transit
        try:
            target = Target.objects.get(pk=self.cleaned_data["target_id"])
        except Target.DoesNotExist:
            return {}
        try:
            transit = Transit.objects.get(
                target=target, number=self.cleaned_data["transit"]
            )
        except Transit.DoesNotExist:
            return {}

        try:
            is_priority = transit.target.targetextra_set.get(
                key="Priority Proposal"
            ).bool_value
        except TargetExtra.DoesNotExist:
            is_priority = False
        proposal = PROPOSALS["priority"] if is_priority else PROPOSALS["low_priority"]

        # get window
        window, duration = self._build_window()

        # build payload
        payload = {
            "name": self.cleaned_data["name"],
            "proposal": proposal,
            "ipp_value": self.cleaned_data["ipp_value"],
            "operator": "SINGLE",
            "observation_type": "NORMAL",
            "requests": [
                {
                    "configurations": [self._build_configuration(duration)],
                    "windows": [window],
                    "location": self._build_location(),
                }
            ],
        }
        return payload


class IAGTransitSingleContactForm(IAGImagingObservationForm):
    name = forms.CharField(max_length=200)
    contact = forms.CharField(max_length=20)

    def __init__(self, *args, **kwargs):
        IAGImagingObservationForm.__init__(self, *args, **kwargs)

        # transit field
        transits = []
        for c in self.transit_contact_choices():
            if c[0] == int(self.initial["transit"]):
                transits.append(c)
        self.fields["transit"] = forms.ChoiceField(choices=transits)

    def layout(self):
        return Div(
            Div(
                Div(
                    "transit",
                    css_class="col",
                ),
                css_class="row",
            ),
            Div(
                Div(
                    "instrument_type",
                    css_class="col",
                ),
                css_class="row",
            ),
            Div(
                Div("readout_mode", css_class="col"),
                Div("filter", css_class="col"),
                css_class="form-row",
            ),
            Div(
                Div("exposure_time", css_class="col"),
                Div("ipp_value", css_class="col"),
                css_class="form-row",
            ),
        )

    def transit_contact_choices(self):
        now = Time.now().isot

        contact_choices = []
        contact_choices.extend(
            [
                (
                    t.number,
                    "#%d: %s Ingress" % (t.number, t.start.strftime("%Y/%m/%d %H:%M")),
                )
                for t in Transit.objects.filter(start__gt=now)
                if t.ingress_visible(self.initial["facility"])
            ]
        )

        contact_choices.extend(
            [
                (
                    t.number,
                    "#%d: %s Egress" % (t.number, t.start.strftime("%Y/%m/%d %H:%M")),
                )
                for t in Transit.objects.filter(start__gt=now)
                if t.egress_visible(self.initial["facility"])
            ]
        )

        contact_choices = sorted(contact_choices, key=lambda x: x[1])
        return contact_choices

    def clean_start(self):
        start = self.cleaned_data["start"]
        return parse(start).isoformat()

    def clean_end(self):
        end = self.cleaned_data["end"]
        return parse(end).isoformat()

    def _build_acquisition_config(self):
        acquisition_config = {"mode": "ON"}

        return acquisition_config

    def _build_guiding_config(self):
        guiding_config = {"mode": "ON"}

        return guiding_config

    def _build_configuration(self, duration):
        return {
            "type": "REPEAT_EXPOSE",
            "repeat_duration": (duration - 12 * u.min).sec,
            "instrument_type": self.cleaned_data["instrument_type"],
            "target": self._build_target_fields(),
            "instrument_configs": self._build_instrument_config(),
            "acquisition_config": self._build_acquisition_config(),
            "guiding_config": self._build_guiding_config(),
            "constraints": {"max_airmass": self.cleaned_data["max_airmass"]},
        }

    def _build_window(self):
        # get target and transit
        target = Target.objects.get(pk=self.cleaned_data["target_id"])
        transit = Transit.objects.get(
            target=target, number=self.cleaned_data["transit"]
        )
        contact = self.cleaned_data["contact"]

        # calculate start, end and duration
        if contact == "INGRESS":
            start = Time(transit.start_earliest()) - 15 * u.min
            end = Time(transit.start_latest()) + 15 * u.min
            duration = end - start
        elif contact == "EGRESS":
            start = Time(transit.end_earliest()) - 15 * u.min
            end = Time(transit.end_latest()) + 15 * u.min
            duration = end - start

        # return it
        return {"start": start.isot, "end": end.isot}, duration

    def _build_instrument_config(self):
        return [
            {
                "exposure_count": 1,
                "exposure_time": self.cleaned_data["exposure_time"],
                "mode": self.cleaned_data["readout_mode"],
                "optical_elements": {"filter": self.cleaned_data["filter"]},
            }
        ]

    def observation_payload(self):
        # get target and transit
        try:
            target = Target.objects.get(pk=self.cleaned_data["target_id"])
        except Target.DoesNotExist:
            return {}
        try:
            transit = Transit.objects.get(
                target=target, number=self.cleaned_data["transit"]
            )
        except Transit.DoesNotExist:
            return {}

        try:
            is_priority = transit.target.targetextra_set.get(
                key="Priority Proposal"
            ).bool_value
        except TargetExtra.DoesNotExist:
            is_priority = False
        proposal = PROPOSALS["priority"] if is_priority else PROPOSALS["low_priority"]

        # get window
        window, duration = self._build_window()

        # build payload
        payload = {
            "name": self.cleaned_data["name"],
            "proposal": proposal,
            "ipp_value": self.cleaned_data["ipp_value"],
            "operator": "SINGLE",
            "observation_type": "NORMAL",
            "requests": [
                {
                    "configurations": [self._build_configuration(duration)],
                    "windows": [window],
                    "location": self._build_location(),
                }
            ],
        }
        return payload


class IAGTransitFacility(IAGFacility):
    """
    The ``LCOFacility`` is the interface to the Las Cumbres Observatory Observation Portal. For information regarding
    LCO observing and the available parameters, please see https://observe.lco.global/help/.
    """

    name = "IAGTransit"
    observation_forms = {"TRANSIT": IAGTransitForm}

    def get_form(self, observation_type):
        try:
            return self.observation_forms[observation_type]
        except KeyError:
            return IAGTransitForm
