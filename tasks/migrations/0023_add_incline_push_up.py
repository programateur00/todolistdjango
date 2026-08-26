# Añade "Flexiones inclinadas" al catálogo de tren superior, a petición
# del usuario.
#
# Es EL MISMO gesto que "Flexiones" (push-up): el codo se dobla y se
# extiende igual, solo que en vez de apoyar los pies en el suelo (cuerpo
# en línea recta, plano) se apoyan en alto (una silla, un escalón, un
# banco...), lo que levanta la cadera por encima de los hombros: en vez
# de la línea horizontal de una flexión normal, el cuerpo queda formando
# una línea ascendente desde las manos (abajo) hasta los pies (arriba).
#
# A DIFERENCIA de "Sentadillas con peso" (0020_add_weighted_squat, que sí
# reutiliza el counter_key de la sentadilla sin peso porque MediaPipe no
# necesita saber que hay peso de más), aquí NO se reutiliza
# counter_key="pushup": a petición de Alex, esta variante tiene que
# contar bien SIN IMPORTAR lo alto que se eleven los pies, y el contador
# de "Flexiones" normal (processPushup, workout.js) usa un TECHO de
# inclinación (ON_GROUND_MAX_TILT_DEG/PUSHUP_BROKEN_TILT_DEG) para saber
# si sigues tumbado o si te has puesto de pie — un techo que precisamente
# cortaría el contador en cuanto los pies estuvieran razonablemente altos.
# Por eso tiene su propio counter_key="inclinepushup" y su propia función
# (processInclinePushup, workout.js). Primera versión (retirada tras
# probarla en cámara real, ver el bloque INCLINE_PUSHUP_* en ese archivo
# para el detalle completo): un SUELO de inclinación en vez de un techo —
# falló porque una flexión plana normal podía superarlo igualmente, y
# porque solo comprobaba la postura al armar, no durante toda la serie
# (un gesto de brazo suelto, ya armado, se contaba como repetición).
# Arreglo: la postura ahora se mide en directo (la muñeca tiene que
# quedar claramente por debajo del tobillo en la imagen, no un ángulo de
# inclinación indirecto) y se comprueba en TODOS los frames mientras la
# serie está armada, cerrándola sola en cuanto se rompe — incluido
# ponerte de pie, que con esta comprobación ya no se confunde con "pies
# muy altos" (de pie, la muñeca queda muy por encima del tobillo, justo
# lo contrario).
#
# body_area="upper_body" (tren superior — igual que "Flexiones").
# Nivel principiante (ver ai._EXERCISE_DIFFICULTY en tasks/ai.py, que hay
# que actualizar a la vez que esta migración — no hay forma de que una
# migración de datos toque ai.py): decisión del usuario — mismo nivel que
# "Flexiones" (beginner), no un escalón por encima.
#
# El slug no tiene ilustración propia (ver exercise_icons.py, que hay que
# actualizar a la vez): reutiliza la silueta de "push-up" vía ALIAS, igual
# que otras variantes que comparten el mismo gesto (weighted-dips,
# wall-sit, kneehold-bar...) — la silueta no distingue counter_key, así
# que puede reutilizarse aunque el contador de cámara sea otro.
#
# Mismo patrón que 0012/0014/0015/0017/0018/0019/0020 (siembra el
# catálogo para instalaciones nuevas, get_or_create idempotente para quien
# ya la haya aplicado): este ejercicio no existía antes en el catálogo,
# así que no hace falta ningún "pasa de estado viejo a nuevo".

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="incline-push-up", name="Flexiones inclinadas", mode="pose", counter_key="inclinepushup", order=24),
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
        ("tasks", "0022_replace_dead_hang_with_handstand"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
