"""
Utilidades compartidas de la app.
"""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model

DEFAULT_USERNAME = "default"

# Carpeta donde caen a mano el APK y su ficha de versión cuando hay una
# build nueva de la app móvil (ver README, "Actualizaciones de la app
# móvil"). Fuera de git (.gitignore) — son binarios, no código.
MOBILE_RELEASES_DIR = Path(settings.BASE_DIR) / "mobile_releases"


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


def read_mobile_release():
    """
    Lee mobile_releases/latest.json EN CADA LLAMADA, sin caché — así
    subir un APK y editar ese archivo se nota en la siguiente petición,
    sin reiniciar nada en PythonAnywhere.

    Formato esperado del JSON (se edita a mano, ver README):
        {"version": "3", "apk_filename": "libreta-v3.apk", "notes": "..."}

    Devuelve None si no hay ninguna build publicada, el JSON está mal
    formado, o el archivo que declara no existe de verdad — en
    cualquiera de esos casos, tanto /api/meta/ como la descarga se
    comportan como si no hubiera ninguna actualización, en vez de dar
    un error. Compartido entre api.py (avisa de la versión nueva) y
    views.py (sirve el archivo) para no leer el JSON de dos formas
    distintas.
    """
    info_path = MOBILE_RELEASES_DIR / "latest.json"
    try:
        data = json.loads(info_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    version = str(data.get("version") or "").strip()
    # .name descarta cualquier ruta que traiga el campo — nunca se sirve
    # un archivo fuera de mobile_releases/, pase lo que pase en el JSON.
    apk_filename = Path(str(data.get("apk_filename") or "").strip()).name
    if not version or not apk_filename:
        return None
    apk_path = MOBILE_RELEASES_DIR / apk_filename
    if not apk_path.is_file():
        return None
    return {
        "version": version,
        "apk_path": apk_path,
        "notes": str(data.get("notes") or "").strip(),
    }
