# Generated by Django 3.1.1 on 2020-09-25 13:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tom_targets", "0018_auto_20200714_1832"),
    ]

    operations = [
        migrations.CreateModel(
            name="Transit",
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
                ("number", models.IntegerField(verbose_name="Transit number")),
                ("start", models.DateTimeField(verbose_name="Time the transit starts")),
                ("mid", models.DateTimeField(verbose_name="Time of mid-transit")),
                ("end", models.DateTimeField(verbose_name="Time the transit ends")),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="tom_targets.target",
                    ),
                ),
            ],
            options={
                "index_together": {("target", "number")},
            },
        ),
    ]
