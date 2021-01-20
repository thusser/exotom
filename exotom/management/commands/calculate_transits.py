from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Calculate transit times for all targets"

    def handle(self, *args, **options):
        from exotom.transits import calculate_transits_during_next_n_days
        from exotom.models import Target

        for target in Target.objects.all():
            calculate_transits_during_next_n_days(target, 10)
