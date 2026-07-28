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

LABELS = {
    "plank": "Plancha", "crunch": "Crunch", "leg-raise": "Elevación de piernas",
    "bicycle-crunch": "Bicicleta", "mountain-climber": "Mountain climbers",
    "superman": "Superman", "squat": "Sentadillas", "situp": "Abdominales",
    "pullup": "Dominadas", "push-up": "Flexiones", "side-plank": "Plancha lateral",
    "dips": "Fondos", "lunge": "Zancadas",
}


@register.simple_tag
def exercise_icon(slug, compact=False):
    label = LABELS.get(slug, "Ejercicio")

    if slug not in AVAILABLE:
        return format_html(
            '<div class="ex-fig ex-fig--empty" role="img" aria-label="{}"><span>{}</span></div>',
            label, label,
        )

    cls = "ex-fig ex-fig--compact" if compact else "ex-fig"

    if slug in STATIC:
        return format_html(
            '<div class="{} ex-fig--static" role="img" aria-label="{}">'
            '<img src="{}" alt=""><span class="ex-fig__hold">mantener</span></div>',
            cls, label, static(f"exercises/{slug}-1.svg"),
        )

    return format_html(
        '<div class="{}" role="img" aria-label="{}: postura inicial y final">'
        '<img src="{}" alt="">'
        '<span class="ex-fig__arrow" aria-hidden="true">→</span>'
        '<img src="{}" alt=""></div>',
        cls, label,
        static(f"exercises/{slug}-1.svg"),
        static(f"exercises/{slug}-2.svg"),
    )
