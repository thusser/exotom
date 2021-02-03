from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Calculate transit times for all targets"

    def add_arguments(self, parser):
        parser.add_argument("--ndays", nargs=1, type=int, default=10)

    def handle(self, *args, **options):
        from exotom.transits import calculate_transits_during_next_n_days
        from exotom.models import Target

        n_days = options["ndays"]
        for target in Target.objects.all():
            calculate_transits_during_next_n_days(target, n_days)
