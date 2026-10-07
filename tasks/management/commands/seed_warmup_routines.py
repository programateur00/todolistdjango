"""
Comando de gestión: crea (o actualiza) dos circuitos de calentamiento y
estiramiento -- uno para tren superior, otro para tren inferior -- para
sustituir el vídeo fijo de YouTube que ofrecían antes task_warmup /
task_cooldown (ver _warmup_routine_for en tasks/views.py). Mezclan
ejercicios de cámara (calentamiento propiamente dicho) con movilidad
articular, con un único set ligero cada uno -- no es un bloque de
fuerza, es la parte de antes/después de la sesión de verdad.

Los ejercicios bilaterales/direccionales (un lado y luego el otro, o un
sentido y luego el otro -- círculos de brazos, estiramientos de brazo
cruzado, etc.) van a DOS series completas, una por lado/sentido -- no
una sola serie repartida entre los dos. Ver la nota junto a ROUTINES.

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
#
# BILATERALES/DIRECCIONALES -- a petición de Alex: cualquier ejercicio
# que se hace "un lado y luego el otro" o "un sentido y luego el otro"
# (círculos de brazos: horario y luego antihorario; giros de cuello;
# zancada dividida: pierna izq. y luego dcha.; estiramientos sujetando
# un brazo/pierna: uno y luego el otro...) lleva DOS series completas
# de 30, no una sola de 30 repartida entre los dos lados/sentidos:
#   - Ejercicios de cámara (pose): target_sets=2 en vez de 1 -- el
#     propio circuito exige acabar la 2ª serie de 30 reps antes de
#     pasar al siguiente ejercicio (cambias de lado/sentido entre
#     serie y serie, eso lo decides tú, no lo fuerza el contador).
#   - Ejercicios cronometrados (timed: brazo cruzado, tríceps por
#     detrás, cuádriceps de pie): no existen "series"
#     para un timed (RoutineItem no las usa en ese modo), así que el
#     mismo slug aparece DOS VECES seguidas en la lista -- dos cuentas
#     atrás de 30s independientes, una por lado.
# Los simétricos (jumping jacks, flexiones, tijera de brazos, rotación
# de muñeca entrelazada, cadera adelante-atrás, rodillas altas, talón
# al glúteo, medio giro de cuello) se quedan con una sola serie: ya
# trabajan los dos lados a la vez o no tienen lado/sentido que alternar.
ROUTINES = [
    {
        "name": "Calentamiento y estiramiento — tren superior",
        "subcategory": Task.SUBCATEGORY_UPPER_BODY,
        # Orden de arriba a abajo del cuerpo: cuello, brazos, muñecas,
        # jumping jacks, flexiones (a petición de Alex).
        "items": [
            # A petición de Alex (2026-09-21): UNA sola serie de 30 por
            # ejercicio, sin dos series por lado/sentido (cada cronometrado
            # aparece una sola vez). Flexiones se quedan en 10.
            ("neck-lateral-mobility", 1, 30),  # oreja al hombro
            ("neck-turn-side", 1, 30),         # el "no" con la cabeza
            # A peticion de Alex (2026-09-29): DOS pantallas seguidas, la 1a
            # hacia delante y la 2a hacia atras (sentido fijado por aparicion,
            # ver DIRECTION_COUNTERS en session-runner.js/circuit.js), 30 cada
            # una, y cada una pasa sola a la siguiente al llegar a 30.
            # A peticion de Alex (2026-10-01): es UN solo ejercicio, hecho DOS
            # veces ("vez 1 de 2" / "vez 2 de 2", como los demas bilaterales) --
            # no dos ejercicios distintos. Por dentro la 1a vez cuenta hacia
            # delante y la 2a hacia atras (ver DIRECTION_COUNTERS), pero en
            # pantalla se presenta solo como el mismo ejercicio repetido.
            ("arm-circles", 1, 30),  # vez 1 de 2
            ("arm-circles", 1, 30),  # vez 2 de 2
            ("arm-scissors", 1, 30),
            # A peticion de Alex (2026-10-01): los dos estiramientos son
            # bilaterales -- DOS pantallas cronometradas seguidas cada uno,
            # una por brazo (antes solo salia una y solo se podia hacer un lado).
            ("arm-cross-stretch", None, None),         # cronometrado, brazo 1
            ("arm-cross-stretch", None, None),         # cronometrado, brazo 2
            ("triceps-overhead-stretch", None, None),  # cronometrado, brazo 1
            ("triceps-overhead-stretch", None, None),  # cronometrado, brazo 2
            # A peticion de Alex (2026-09-25): igual que los
            # estiramientos cronometrados de abajo -- DOS pantallas
            # seguidas, una por brazo, en vez de una sola serie
            # combinando los dos lados con cambio de brazo a mitad
            # (ver REP_SIDE_COUNTERS en circuit.js/session-runner.js).
            ("forearm-rotation-elbow-hold", 1, 30),  # brazo 1
            ("forearm-rotation-elbow-hold", 1, 30),  # brazo 2
            ("jumping-jack", 1, 30),
            ("push-up", 1, 10),
            # A peticion de Alex (2026-09-28): tras flexiones, aguantarse en la
            # barra (dead hang, cronometrado -- usa el work/rest por defecto
            # de la rutina, 30s) y dominada escapular (12 reps).
            ("dead-hang", None, None),        # cronometrado, 30s (default_work_seconds)
            ("scapular-pull", 1, 12),
        ],
    },
    {
        "name": "Calentamiento y estiramiento — tren inferior",
        "subcategory": Task.SUBCATEGORY_LOWER_BODY,
        # Mismo criterio que tren superior: de arriba a abajo del cuerpo,
        # con jumping jacks y rodillas altas como los dos últimos.
        "items": [
            ("hip-forward-back", 1, 30),          # simétrico (adelante-atrás con las dos caderas)
            ("hip-lateral-mobility", 1, 30),      # una sola serie de 30 (Alex, 2026-09-24)
            ("split-squat-warmup", 1, 15),        # una sola serie de 15 (Alex, 2026-09-30; antes 30)
            ("leg-rotation", 1, 30),              # una sola serie de 30 (Alex, 2026-09-24)
            ("jumping-jack", 1, 30),
            ("knee-raises", 1, 30),
            ("heel-kicks", 1, 30),
            # Alex (2026-10-06): quitada la elevación de pierna alta de este calentamiento.
            # A peticion de Alex (2026-09-30): elephant steps (aguante) en
            # lugar del estiramiento de isquios sentado. Cronometrado y
            # simetrico (las dos piernas a la vez) -- una sola pantalla.
            ("elephant-steps-hold", None, None),       # cronometrado, simetrico
            ("standing-quad-stretch", None, None),     # cronometrado, bilateral -- serie 1: una pierna
            ("standing-quad-stretch", None, None),     # cronometrado, bilateral -- serie 2: la otra pierna
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
                    "default_rest_seconds": 0,
                    "is_warmup_bookend": True,
                },
            )
            if not created:
                routine.subcategory = plan["subcategory"]
                routine.default_work_seconds = 30
                routine.default_rest_seconds = 0
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
