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
STATIC = {"plank", "side-plank"}

# Variantes que comparten dibujo: el movimiento es el mismo y solo cambia
# el agarre (ancho, supino) o si añades peso o impulso. Repetir la
# ilustración es más honesto que dejar un hueco.
ALIAS = {
    "wide-pullup": "pullup",
    "chinup": "pullup",
    "weighted-pullup": "pullup",
    "jumping-pullup": "pullup",
}

LABELS = {
    "plank": "Plancha", "crunch": "Crunch", "leg-raise": "Elevación de piernas",
    "bicycle-crunch": "Bicicleta", "mountain-climber": "Mountain climbers",
    "superman": "Superman", "squat": "Sentadillas", "situp": "Abdominales",
    "pullup": "Dominadas", "push-up": "Flexiones", "side-plank": "Plancha lateral",
    "dips": "Fondos", "lunge": "Zancadas",
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

    is_static = art in STATIC
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
