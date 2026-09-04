# Añade "Fondos en banco" (bench dip) al catálogo de tren superior, a
# petición del usuario.
#
# Variante de fondos donde, en vez de paralelas, las manos se apoyan
# detrás del cuerpo en una superficie elevada (un banco, una silla, el
# borde de un sofá) y los pies se apoyan en el suelo por delante — el
# cuerpo entero forma una "L". Mismo gesto de brazo que un fondo normal
# (el codo se dobla hasta ~90° y vuelve a estirarse para contar la
# repetición), así que se cuenta por REPETICIONES (mode="pose"), no
# cronometrado.
#
# Su propio counter_key="benchdip" (NO reutiliza "dip"): a diferencia de
# "Sentadillas con peso" (0020_add_weighted_squat, que sí reutiliza el
# counter_key de la sentadilla sin peso porque MediaPipe no necesita
# saber que hay peso de más), aquí el gesto SÍ cambia lo bastante como
# para necesitar su propia comprobación de postura — processDip da por
# hecho que estás de pie junto a unas paralelas y calibra tu altura de
# hombro/cadera de pie antes de nada, algo que no existe en un fondo en
# banco (sentado, con los pies en el suelo desde el principio). Su
# propia función (processBenchDip, workout.js) sigue en cambio el patrón
# de processInclinePushup (mismo tipo de comprobación directa de
# landmarks en vez de calibración) — ver el bloque BENCHDIP_* de ese
# archivo para el detalle completo del diseño: ángulo de codo
# (DIP_UP_ANGLE_DEG/DIP_DOWN_ANGLE_DEG, reutilizados de fondos normales)
# para contar la repetición, más dos comprobaciones de postura en
# directo, en TODOS los frames mientras la serie está armada: manos
# claramente por encima del nivel de los pies (a petición explícita del
# usuario) y el cuerpo formando una "L" (ángulo hombro-cadera-tobillo
# cerca de 90°, no cerca de 180° como en una flexión o plancha). No se
# cuenta ninguna repetición hasta volver a la posición inicial (brazos
# rectos + cuerpo en L) tras pasar por abajo (codo a 90°).
#
# body_area="upper_body" (tren superior — misma familia que "Fondos").
# Nivel principiante (ver ai._EXERCISE_DIFFICULTY en tasks/ai.py, que hay
# que actualizar a la vez que esta migración — no hay forma de que una
# migración de datos toque ai.py): decisión explícita del usuario, a
# pesar de que "Fondos" (paralelas) normales son "intermediate" — el
# apoyo en banco (más estable, sin necesidad de sostener todo el peso
# del cuerpo en el aire desde el principio) lo hace más accesible.
#
# El slug no tiene ilustración propia (ver exercise_icons.py, que hay
# que actualizar a la vez, y su equivalente en la app móvil,
# exercise-icons.js): reutiliza la silueta de "dips" vía ALIAS, misma
# familia de movimiento (flexión de codo bajo el propio peso), igual que
# weighted-dips ya hace.
#
# Contador de cámara nuevo ("benchdip"): hay que añadirlo también a
# COUNTERS en views.py y a su equivalente en la app móvil
# (workout-view.js) para que is_pose_supported lo reconozca — ninguno de
# los dos se puede tocar desde una migración de datos.
#
# Mismo patrón que 0012/0014/0015/0017/0018/0019/0020/0023/0024 (siembra
# el catálogo para instalaciones nuevas, get_or_create idempotente para
# quien ya la haya aplicado): este ejercicio no existía antes en el
# catálogo, así que no hace falta ningún "pasa de estado viejo a nuevo".

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="bench-dip", name="Fondos en banco", mode="pose", counter_key="benchdip", order=26),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0029_add_warmup_subcategory"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
