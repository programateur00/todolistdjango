"""
Recalcula Occurrence.completion_pct de los días ya guardados a partir de
las sesiones (WorkoutSession / TimerSession) de cada tarea: la media del %
de todos los ejercicios de ese día (ver Task.day_completion_pct).

    python manage.py backfill_completion_pct            # solo filas sin calcular
    python manage.py backfill_completion_pct --all      # recalcula todas
    python manage.py backfill_completion_pct --dry-run  # solo cuenta, no guarda
"""
from django.core.management.base import BaseCommand

from tasks.models import Occurrence


class Command(BaseCommand):
    help = "Calcula el % de cumplimiento de los días antiguos a partir de sus sesiones."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Recalcular también las ya guardadas.")
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada.")

    def handle(self, *args, **opts):
        qs = Occurrence.objects.select_related("task")
        if not opts["all"]:
            qs = qs.filter(completion_pct__isnull=True)
        changed = total = 0
        for occ in qs.iterator():
            total += 1
            if occ.task is not None:
                pct = occ.task.day_completion_pct(occ.result)
            else:  # tarea borrada: no hay sesiones a las que mirar
                pct = 100 if occ.result == Occurrence.RESULT_DONE else 0
            if occ.completion_pct != pct:
                changed += 1
                if not opts["dry_run"]:
                    occ.completion_pct = pct
                    occ.save(update_fields=["completion_pct"])
        self.stdout.write(f"{total} días revisados, {changed} {'cambiarían' if opts['dry_run'] else 'actualizados'}.")
