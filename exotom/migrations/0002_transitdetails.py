# Generated by Django 3.1.1 on 2020-09-28 13:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("exotom", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TransitDetails",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("site", models.TextField(verbose_name="Name of site.")),
                (
                    "target_alt_start",
                    models.FloatField(
                        verbose_name="Elevation of target at start of transit"
                    ),
                ),
                (
                    "target_alt_mid",
                    models.FloatField(
                        verbose_name="Elevation of target at start of transit"
                    ),
                ),
                (
                    "target_alt_end",
                    models.FloatField(
                        verbose_name="Elevation of target at start of transit"
                    ),
                ),
                (
                    "sun_alt_mid",
                    models.FloatField(verbose_name="Elevation of sun at mid-transit."),
                ),
                (
                    "moon_alt_mid",
                    models.FloatField(verbose_name="Elevation of moon at mid-transit."),
                ),
                (
                    "moon_dist_mid",
                    models.FloatField(verbose_name="Distance to moon at mid-transit."),
                ),
                (
                    "observable",
                    models.BooleanField(verbose_name="Whether transit is observable"),
                ),
                (
                    "transit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="exotom.transit"
                    ),
                ),
            ],
            options={
                "index_together": {("transit", "site")},
            },
        ),
    ]
