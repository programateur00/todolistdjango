"""
Ilustraciones de ejercicios para las plantillas.

Son dibujos reales (siluetas anatómicas) del proyecto Everkinetic, con
dos posturas por ejercicio: inicio y final. Se muestran las dos a la vez,
como en un libro de ejercicios — se entiende el movimiento de un vistazo.

Los archivos están en static/exercises/<slug>-1.svg y -2.svg.

Licencia: Creative Commons Attribution-ShareAlike 3.0, autor Everkinetic.
El crédito tiene que seguir visible (ver la plantilla base).

Uso:  {% load exercise_icons %}{% exercise_icon "plank" %}
"""
from django import template
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()

# Ejercicios con ilustración propia. El resto muestra un hueco discreto.
AVAILABLE = {
    "crunch", "leg-raise", "superman", "bicycle-crunch", "plank",
    "squat", "situp", "pullup", "push-up", "side-plank", "dips", "lunge",
}

# Isométricos: no hay dos posturas, así que se enseña una y se indica
# que hay que aguantar, en vez de fingir un movimiento.
STATIC = {"plank", "side-plank", "wall-sit", "kneehold-bar"}

# Variantes que comparten dibujo: el movimiento es el mismo y solo cambia
# el agarre (ancho, supino) o si añades peso o impulso. Repetir la
# ilustración es más honesto que dejar un hueco.
#
# double-crunch y scissor-kick son ejercicios nuevos y todavía no tienen
# dibujo propio: se prestan la silueta del ejercicio existente que más
# se parece en postura, en vez de dejar el hueco discreto.
#   - double-crunch: tumbado boca arriba con el torso ya levantado del
#     suelo (postura intermedia mantenida) mientras las piernas se
#     flexionan — visualmente es un abdominal (situp) con las rodillas
#     dobladas, así que reutiliza esa silueta.
#   - scissor-kick: tumbado boca arriba con las piernas rectas alternando
#     altura sobre el suelo — el mismo gesto que leg-raise, solo que
#     alternando de pierna, así que reutiliza esa silueta.
#   - wall-sit: rodillas dobladas a 90°, muslos paralelos al suelo — la
#     misma postura de piernas que el punto más bajo de una sentadilla
#     (squat), solo que aguantada contra una pared en vez de en
#     movimiento, así que reutiliza esa silueta.
#   - kneehold-bar: colgado de la barra con los brazos estirados — misma
#     postura de partida que las dominadas (pullup), solo que en vez de
#     subir y bajar se suben las rodillas y se aguantan; reutiliza esa
#     silueta.
#   - archer-pullup: misma postura de partida (colgado de la barra) y el
#     mismo gesto de subir tirando con los brazos que una dominada
#     normal — lo único que cambia es que un brazo se dobla más que el
#     otro al llegar arriba, algo que esta silueta de dos posturas no
#     distingue de todas formas, así que reutiliza la de pullup en vez
#     de dejar el hueco discreto.
#
# handstand (el pino) NO tiene alias: ninguna silueta de Everkinetic que
# tenemos (todas de pie o tumbadas) se parece a un cuerpo invertido, así
# que cae al hueco discreto de solo texto en vez de tomar prestado un
# dibujo que confundiría más de lo que ayuda.
ALIAS = {
    "wide-pullup": "pullup",
    "chinup": "pullup",
    "weighted-pullup": "pullup",
    "jumping-pullup": "pullup",
    "weighted-dips": "dips",
    "double-crunch": "situp",
    "scissor-kick": "leg-raise",
    "wall-sit": "squat",
    "kneehold-bar": "pullup",
    "archer-pullup": "pullup",
}

LABELS = {
    "plank": "Plancha", "crunch": "Crunch", "leg-raise": "Elevación de piernas",
    "bicycle-crunch": "Bicicleta", "mountain-climber": "Mountain climbers",
    "superman": "Superman", "squat": "Sentadillas", "situp": "Abdominales",
    "pullup": "Dominadas", "push-up": "Flexiones", "side-plank": "Plancha lateral",
    "dips": "Fondos", "lunge": "Zancadas", "weighted-dips": "Fondos con peso",
    "double-crunch": "Doble crunch", "scissor-kick": "Scissor Kicks",
    "wall-sit": "Silla en pared", "kneehold-bar": "Kneehold Bar",
    "handstand": "Handstand", "archer-pullup": "Dominadas de arquero",
}


@register.simple_tag
def exercise_icon(slug, compact=False):
    """Bloque del ejercicio con sus dos posturas alternándose."""
    label = LABELS.get(slug, "Ejercicio")
    art = ALIAS.get(slug, slug)   # las variantes reutilizan el dibujo base

    if art not in AVAILABLE:
        return format_html(
            '<div class="ex-fig ex-fig--empty" role="img" aria-label="{}"><span>{}</span></div>',
            label, label,
        )

    # OJO: se comprueba el SLUG original, no `art` — un ejercicio puede
    # tomar prestado el dibujo de otro que no es isométrico (wall-sit
    # reutiliza el de squat, que sí tiene dos posturas de movimiento) y
    # aun así necesitar el badge "mantener" él mismo.
    is_static = slug in STATIC
    cls = " ".join(filter(None, [
        "ex-fig",
        "ex-fig--compact" if compact else "",
        "ex-fig--static" if is_static else "",
    ]))
    hold = mark_safe('<span class="ex-fig__hold">mantener</span>') if is_static else ""

    return format_html(
        '<div class="{}" role="img" aria-label="{}">'
        '<img src="{}" alt=""><img src="{}" alt="">{}</div>',
        cls, label,
        static(f"exercises/{art}-1.svg"),
        static(f"exercises/{art}-2.svg"),
        hold,
    )
