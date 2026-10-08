"""
Rellena WorkoutSession.added_weight_kg en las sesiones con peso guardadas
ANTES de que la sesión copiara sola el peso del plan (08/10/2026), para que
la gráfica de progreso del plan enseñe los kg de esas sesiones.

El peso real de aquel día no se guardó, así que se reconstruye: se repasan
las sesiones de cada objetivo en orden y, para cada una, se calcula en qué
escalón estaba el plan JUSTO ANTES (mismas reglas que PlanItem.current_step:
sesiones cumplidas // sessions_per_step, con bajada por fallos seguidos) y
se toma el peso de ese escalón. Es lo que habría copiado save() de haber
existido. Vale si el objetivo no se ha editado desde entonces.

Solo toca sesiones de ejercicios con lastre, de un plan, con
added_weight_kg vacío. Nunca pisa un peso ya guardado.

    python manage.py backfill_added_weight --dry-run   # enseña, no guarda
    python manage.py backfill_added_weight             # guarda
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from tasks.models import Exercise, PlanItem, WorkoutSession


class Command(BaseCommand):
    help = "Reconstruye los kg añadidos de las sesiones con peso antiguas."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        filled = skipped = 0
        items = (PlanItem.objects.filter(exercise__slug__in=Exercise.WEIGHTED_SLUGS)
                 .select_related("plan", "exercise").order_by("plan_id", "order", "id"))
        seen = set()
        for it in items:
            key = (it.plan_id, it.exercise.slug)
            if key in seen:  # save() usa solo el primer objetivo del ejercicio
                continue
            seen.add(key)
            sessions = list(it._sessions())
            results = []  # ¿se cumplió cada sesión anterior?
            for ws in sessions:
                if ws.added_weight_kg is None:
                    successes = sum(results)
                    streak = 0
                    for r in reversed(results):
                        if r:
                            break
                        streak += 1
                    step = successes // max(1, it.sessions_per_step)
                    if it.deload_after_failures and streak >= it.deload_after_failures:
                        step = max(0, step - 1)
                    kg = it.target_for_step(step).get("weight_kg")
                    if kg:
                        filled += 1
                        self.stdout.write(f"  {it.plan.name} · {it.exercise.slug} · "
                                          f"{timezone.localtime(ws.recorded_at):%d/%m/%Y} -> +{kg:g} kg")
                        if not dry:
                            # updated_at a mano: update() no lo toca y la app móvil
                            # sincroniza por ahí.
                            WorkoutSession.objects.filter(pk=ws.pk).update(
                                added_weight_kg=float(kg), updated_at=timezone.now())
                    else:
                        skipped += 1
                results.append((ws.achievement_pct or 0) >= 100)
        self.stdout.write(f"{filled} sesiones rellenadas, {skipped} sin peso en el plan."
                          + (" (dry-run: nada guardado)" if dry else ""))
