"""
Utilidades compartidas de la app.
"""
from django.contrib.auth import get_user_model

DEFAULT_USERNAME = "default"


def get_current_user():
    """
    Devuelve el "usuario actual" de la app.

    HOY: todoapp/basic_auth.py protege la app entera con una única
    contraseña por variables de entorno — no usa el sistema de usuarios de
    Django, así que no existe ningún request.user real. Por eso esta
    función siempre devuelve el mismo usuario por defecto (creándolo la
    primera vez que hace falta), y todas las vistas filtran/asignan a
    través de ella en vez de tocar el modelo User directamente.

    CUANDO HAYA LOGIN DE VERDAD: cambia el cuerpo de esta función para que
    reciba el request y devuelva request.user (o conviértela en un
    decorador/mixin que exija sesión iniciada). Como todas las consultas
    de tasks/views.py ya pasan por aquí, el filtrado por usuario empieza a
    funcionar de verdad sin tocar nada más en las vistas.
    """
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=DEFAULT_USERNAME,
        defaults={"is_active": True},
    )
    return user


def resolve_plan_target(exercise_slug, sets=None, reps=None, seconds=None):
    """
    A qué plan cuenta una sesión de este ejercicio, y qué objetivo tenía.

    Compartido entre la web (views.py) y la API (api.py) a propósito: si
    solo viviera en uno de los dos, entrenar desde el otro no contaría
    para el plan (antes era justo lo que pasaba con la web). El
    ejercicio puede venir de CUALQUIER tarea, no solo de la que generó
    el plan — si hay un plan activo siguiéndolo, manda el plan.

    El objetivo se guarda EN la sesión y no se recalcula después, porque
    sube con las sesiones: si se recalculara, un entreno de hace un mes
    se compararía con el objetivo de hoy y el porcentaje saldría falso.

    Si quien llama ya trae su propio objetivo (`sets`/`reps`/`seconds` —
    el que tenía delante mientras entrenaba), se respeta y solo se
    completa lo que falte desde el plan.
    """
    from .models import PlanItem  # import local: evita el ciclo con models.py

    entry = (
        PlanItem.objects
        .filter(
            exercise__slug=exercise_slug,
            plan__is_active=True,
            plan__deleted_at__isnull=True,
            plan__user=get_current_user(),
        )
        .select_related("plan")
        .order_by("-plan__started_on")
        .first()
    )
    if not entry:
        return {"plan": None, "target_sets": sets, "target_reps": reps, "target_seconds": seconds}

    t = entry.current_target()
    return {
        "plan": entry.plan,
        "target_sets": sets if sets is not None else t["sets"],
        "target_reps": reps if reps is not None else t["reps"],
        "target_seconds": seconds if seconds is not None else t["seconds"],
    }
