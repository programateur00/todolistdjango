"""
Calcula WorkoutSession.calories_kcal de las sesiones ya guardadas (ver
tasks/calories.py). Usa el peso corporal que haya ahora en Ajustes.

    python manage.py backfill_calories            # solo las que no tienen
    python manage.py backfill_calories --all      # recalcula todas
    python manage.py backfill_calories --dry-run  # solo cuenta, no guarda
"""
from django.core.management.base import BaseCommand

from tasks.calories import estimate_workout_calories
from tasks.models import WorkoutSession


class Command(BaseCommand):
    help = "Calcula las calorías aproximadas de las sesiones de entreno antiguas."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Recalcular también las ya guardadas.")
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada.")

    def handle(self, *args, **opts):
        qs = WorkoutSession.objects.select_related("user")
        if not opts["all"]:
            qs = qs.filter(calories_kcal__isnull=True)
        done = skipped = 0
        for ws in qs:
            kcal = estimate_workout_calories(ws)
            if kcal is None:
                skipped += 1
                continue
            done += 1
            if not opts["dry_run"]:
                WorkoutSession.objects.filter(pk=ws.pk).update(calories_kcal=kcal)
        self.stdout.write(f"{done} sesiones calculadas, {skipped} sin datos suficientes."
                          + (" (dry-run: nada guardado)" if opts["dry_run"] else ""))
