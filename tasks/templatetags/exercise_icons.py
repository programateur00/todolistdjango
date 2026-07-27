"""
Ilustraciones (stick-figure, SVG) de cómo se hace cada ejercicio.

Van como diccionario de plantillas en vez de archivos estáticos porque son
muchas piezas pequeñas — así añadir un ejercicio nuevo es una entrada más
en ICONS, sin tocar collectstatic ni preocuparse del cache-busting de
whitenoise. Usan currentColor / var(--paper) para heredar el tema de la
app tal cual esté (funciona porque el SVG queda inline en el HTML, no en
un <img>).

Uso en plantilla:  {% load exercise_icons %}{% exercise_icon "plank" %}
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_FLOOR = (
    '<line x1="5" y1="80" x2="115" y2="80" stroke="currentColor" '
    'stroke-opacity="0.25" stroke-width="3" stroke-dasharray="4 4"/>'
)

_WRAP = (
    '<svg viewBox="0 0 120 90" xmlns="http://www.w3.org/2000/svg" '
    'class="exercise-icon" role="img" aria-label="{label}">'
    '<g fill="none" stroke="currentColor" stroke-width="6" '
    'stroke-linecap="round" stroke-linejoin="round">{floor}{body}</g></svg>'
)

# Cada body es una lista de <line>/<circle> en un lienzo 0 0 120 90.
# Cabeza siempre: circle r="7" fill="var(--paper, #FFFDF8)" (hueco, no
# solido, para que se lea como cabeza y no como un punto ciego).
_BODIES = {
    "plank": """
        <line x1="30" y1="80" x2="15" y2="80" />
        <line x1="30" y1="80" x2="33" y2="46" />
        <line x1="33" y1="46" x2="72" y2="50" />
        <line x1="72" y1="50" x2="104" y2="70" />
        <line x1="104" y1="70" x2="108" y2="80" />
        <circle cx="17" cy="36" r="7" fill="var(--paper, #FFFDF8)"/>
    """,
    "crunch": """
        <line x1="55" y1="80" x2="55" y2="60" />
        <line x1="55" y1="60" x2="35" y2="80" />
        <line x1="55" y1="60" x2="70" y2="50" />
        <line x1="70" y1="50" x2="92" y2="42" />
        <line x1="92" y1="42" x2="100" y2="32" />
        <circle cx="103" cy="27" r="7" fill="var(--paper, #FFFDF8)"/>
    """,
    "leg-raise": """
        <line x1="18" y1="80" x2="55" y2="80" />
        <line x1="55" y1="80" x2="80" y2="18" />
        <line x1="30" y1="80" x2="30" y2="66" />
        <circle cx="14" cy="76" r="7" fill="var(--paper, #FFFDF8)"/>
    """,
    "bicycle-crunch": """
        <line x1="60" y1="65" x2="90" y2="55" />
        <line x1="60" y1="65" x2="45" y2="48" />
        <line x1="45" y1="48" x2="58" y2="38" />
        <line x1="58" y1="38" x2="78" y2="30" />
        <line x1="78" y1="30" x2="58" y2="40" />
        <circle cx="82" cy="25" r="7" fill="var(--paper, #FFFDF8)"/>
    """,
    "mountain-climber": """
        <line x1="30" y1="80" x2="15" y2="80" />
        <line x1="30" y1="80" x2="33" y2="46" />
        <line x1="33" y1="46" x2="75" y2="50" />
        <line x1="75" y1="50" x2="98" y2="66" />
        <line x1="98" y1="66" x2="102" y2="80" />
        <line x1="75" y1="50" x2="58" y2="64" />
        <line x1="58" y1="64" x2="66" y2="78" />
        <circle cx="17" cy="36" r="7" fill="var(--paper, #FFFDF8)"/>
    """,
    "superman": """
        <line x1="50" y1="55" x2="20" y2="42" />
        <line x1="50" y1="55" x2="80" y2="50" />
        <line x1="80" y1="50" x2="106" y2="40" />
        <circle cx="14" cy="39" r="7" fill="var(--paper, #FFFDF8)"/>
    """,
    # Genérico: figura de pie neutra, de respaldo para ejercicios sin
    # ilustración propia todavía (mejor esto que un hueco en blanco).
    "generic": """
        <line x1="60" y1="45" x2="60" y2="70" />
        <line x1="60" y1="70" x2="48" y2="80" />
        <line x1="60" y1="70" x2="72" y2="80" />
        <line x1="60" y1="50" x2="44" y2="58" />
        <line x1="60" y1="50" x2="76" y2="58" />
        <circle cx="60" cy="35" r="7" fill="var(--paper, #FFFDF8)"/>
    """,
}

_LABELS = {
    "plank": "Plancha", "crunch": "Crunch", "leg-raise": "Elevación de piernas",
    "bicycle-crunch": "Bicicleta", "mountain-climber": "Mountain climbers",
    "superman": "Superman", "generic": "Ejercicio",
}


@register.simple_tag
def exercise_icon(slug):
    """Devuelve el SVG (inline, seguro) de cómo se hace `slug`. Si no hay
    ilustración específica, cae a una figura genérica en vez de nada."""
    body = _BODIES.get(slug, _BODIES["generic"])
    label = _LABELS.get(slug, "Ejercicio")
    floor = _FLOOR if slug != "generic" else ""
    return mark_safe(_WRAP.format(label=label, floor=floor, body=body))
