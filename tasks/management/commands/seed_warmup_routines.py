"""
Comando de gestión: crea (o actualiza) dos circuitos de calentamiento y
estiramiento -- uno para tren superior, otro para tren inferior -- para
sustituir el vídeo fijo de YouTube que ofrecían antes task_warmup /
task_cooldown (ver _warmup_routine_for en tasks/views.py). Mezclan
ejercicios de cámara (calentamiento propiamente dicho) con movilidad
articular, con un único set ligero cada uno -- no es un bloque de
fuerza, es la parte de antes/después de la sesión de verdad.

Idempotente: si ya existe un Routine con ese nombre para este usuario,
se actualiza (borra y vuelve a crear sus RoutineItem) en vez de
duplicarlo -- para poder reajustar la lista de ejercicios re-lanzando
el comando sin acumular circuitos repetidos.

Uso:
    python3 manage.py seed_warmup_routines
"""
from django.core.management.base import BaseCommand

from tasks.models import Exercise, Routine, RoutineItem, Task
from tasks.utils import get_current_user

# (slug, target_sets, target_reps) -- un solo set de cada, salvo
# jumping jacks (activador general) y flexiones (primer de fuerza,
# aparte del calentamiento propiamente dicho) que llevan su propio
# número. Los ejercicios de movilidad (cuello/muñeca/cadera/pierna)
# van a 30 reps -- ajustado a petición de Alex (antes 8).
ROUTINES = [
    {
        "name": "Calentamiento y estiramiento — tren superior",
        "subcategory": Task.SUBCATEGORY_UPPER_BODY,
        # Orden de arriba a abajo del cuerpo: cuello, brazos, muñecas,
        # jumping jacks, flexiones (a petición de Alex).
        "items": [
            ("neck-circles", 1, 30),
            ("neck-lateral-mobility", 1, 30),
            ("arm-circles", 1, 30),
            ("arm-scissors", 1, 30),
            ("arm-cross-stretch", None, None),        # cronometrado: brazo estirado, sujeto con el otro
            ("triceps-overhead-stretch", None, None),  # cronometrado: brazo hacia atrás, sujeto con el otro
            ("wrist-rotation-interlaced", 1, 30),
            ("jumping-jack", 1, 30),
            ("push-up", 1, 10),
        ],
    },
    {
        "name": "Calentamiento y estiramiento — tren inferior",
        "subcategory": Task.SUBCATEGORY_LOWER_BODY,
        # Mismo criterio que tren superior: de arriba a abajo del cuerpo,
        # con jumping jacks y rodillas altas como los dos últimos.
        "items": [
            ("hip-forward-back", 1, 30),
            ("hip-lateral-mobility", 1, 30),
            ("split-squat-warmup", 1, 30),
            ("leg-rotation", 1, 30),
            ("jumping-jack", 1, 30),
            ("knee-raises", 1, 30),
            ("seated-hamstring-stretch", None, None),  # cronometrado, al final
        ],
    },
]


class Command(BaseCommand):
    help = "Crea/actualiza los circuitos de calentamiento-estiramiento de tren superior e inferior."

    def handle(self, *args, **options):
        user = get_current_user()

        for plan in ROUTINES:
            routine, created = Routine.objects.get_or_create(
                user=user, name=plan["name"],
                defaults={
                    "subcategory": plan["subcategory"],
                    "default_work_seconds": 30,
                    "default_rest_seconds": 10,
                    "is_warmup_bookend": True,
                },
            )
            if not created:
                routine.subcategory = plan["subcategory"]
                routine.default_work_seconds = 30
                routine.default_rest_seconds = 10
                routine.is_warmup_bookend = True
                routine.save()
                routine.items.all().delete()

            # Por si ya había otro circuito marcado como bookend de esta
            # subcategoría (creado a mano desde la app) -- solo uno a la vez.
            Routine.objects.filter(
                user=user, subcategory=plan["subcategory"], is_warmup_bookend=True,
            ).exclude(pk=routine.pk).update(is_warmup_bookend=False)

            order = 0
            missing = []
            for slug, sets, reps in plan["items"]:
                exercise = Exercise.objects.filter(slug=slug, is_active=True).first()
                if not exercise:
                    missing.append(slug)
                    continue
                # None/None -> ejercicio cronometrado: target_sets/reps no
                # se usan en ese modo, se deja el default del modelo (3x8,
                # irrelevante aquí) y dura lo que diga el work/rest de la
                # rutina (ver default_work_seconds/default_rest_seconds).
                kwargs = {}
                if sets is not None:
                    kwargs["target_sets"] = sets
                if reps is not None:
                    kwargs["target_reps"] = reps
                RoutineItem.objects.create(
                    routine=routine, exercise=exercise, order=order, **kwargs,
                )
                order += 1

            verbo = "Creado" if created else "Actualizado"
            self.stdout.write(self.style.SUCCESS(
                f"{verbo}: «{routine.name}» (subcategoría: {routine.get_subcategory_display()}) "
                f"con {order} ejercicio(s)."
            ))
            if missing:
                self.stdout.write(self.style.WARNING(
                    f"  No encontrados en el catálogo (omitidos): {', '.join(missing)}"
                ))
