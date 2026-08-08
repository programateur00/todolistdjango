"""
Comando de gestión: borra TODOS los datos personales — tareas,
historial, planes, circuitos propios, vídeos guardados, sesiones — para
poder empezar de cero. El catálogo de ejercicios (Exercise) NO se toca:
es del propio catálogo de la app, no algo tuyo, y sin él la app se
queda sin ejercicios que ofrecer.

Es irreversible. Por eso:
  - Pide confirmación escrita a mano, salvo que se pase --yes.
  - Tiene --dry-run para ver antes cuántas filas se borrarían de cada
    cosa, sin tocar nada todavía.

Uso:
    python3 manage.py wipe_data --dry-run     # solo mira, no borra
    python3 manage.py wipe_data               # pide confirmación y borra
    python3 manage.py wipe_data --yes         # borra sin preguntar (con cuidado)

Antes de usarlo de verdad en producción: descarga una copia de
db.sqlite3 primero, por si acaso.
"""

from django.core.management.base import BaseCommand

from tasks.models import (
    Occurrence, Plan, PlanItem, Routine, RoutineItem, SavedVideo, Task, TimerSession, WorkoutSession,
)

# Orden pensado para que los contadores salgan claros, no porque haga
# falta un orden exacto (los on_delete=CASCADE/SET_NULL ya lo resuelven
# solos) — pero borrar explícito cada modelo, en vez de fiarse solo de
# las cascadas, deja un resumen honesto de qué se ha ido.
MODELS_TO_WIPE = [
    ("Ocurrencias (historial de tareas)", Occurrence),
    ("Sesiones de entreno (WorkoutSession)", WorkoutSession),
    ("Sesiones de Enfoque (TimerSession)", TimerSession),
    ("Vídeos guardados", SavedVideo),
    ("Objetivos de plan (PlanItem)", PlanItem),
    ("Planes", Plan),
    ("Ejercicios de circuito (RoutineItem)", RoutineItem),
    ("Circuitos (Routine)", Routine),
    ("Tareas", Task),
]


class Command(BaseCommand):
    help = "Borra todos los datos personales (tareas, historial, planes...). El catálogo de ejercicios no se toca."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes", action="store_true",
            help="No pedir confirmación por teclado (para usar en un script).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo enseña cuántas filas se borrarían de cada modelo, sin borrar nada.",
        )

    def handle(self, *args, **options):
        counts = {label: model.objects.count() for label, model in MODELS_TO_WIPE}
        total = sum(counts.values())

        self.stdout.write("Esto es lo que hay ahora mismo:")
        for label, n in counts.items():
            self.stdout.write(f"  {label}: {n}")
        self.stdout.write(self.style.WARNING(f"Total: {total} filas.\n"))

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No hay nada que borrar."))
            return

        if options["dry_run"]:
            self.stdout.write("(--dry-run: no se ha borrado nada todavía)")
            return

        if not options["yes"]:
            resp = input(
                'Esto borra TODO lo de arriba, sin poder deshacerlo. '
                'Escribe "borrar todo" para confirmar: '
            )
            if resp.strip().lower() != "borrar todo":
                self.stdout.write(self.style.ERROR("Cancelado — no se ha borrado nada."))
                return

        for label, model in MODELS_TO_WIPE:
            deleted, _ = model.objects.all().delete()
            self.stdout.write(f"  {label}: {deleted} borradas")

        self.stdout.write(self.style.SUCCESS(f"\nListo. {total} filas borradas. El catálogo de ejercicios sigue intacto."))
