"""
Formato de ritmo (segundos por km) para las plantillas de planes.

PlanItem.start_pace_seconds_per_km / goal_pace_seconds_per_km / y cada
fila de target_for_step() guardan el ritmo en segundos por km (mismo
formato que Task.max_pace_seconds_per_km, para poder copiarlo tal cual
de un lado a otro sin traducir nada — ver el comentario en models.py).
Pero enseñado en crudo ("390") no se lee — hace falta "6:30/km", que es
como ya se presentan los presets de ritmo en el desplegable del
formulario (Task.PACE_PRESETS). Antes de este filtro, plan_detail.html y
_plan_item.html no tenían forma de mostrar esto y directamente omitían
el ritmo (y la distancia) del objetivo de running.

Uso:  {% load plan_format %}{{ item.start_pace_seconds_per_km|pace_label }}
"""
from django import template

register = template.Library()


@register.filter
def pace_label(seconds):
    """420 -> '7:00/km'. None o 0 -> cadena vacía (no hay ritmo que enseñar)."""
    if not seconds:
        return ""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}/km"
