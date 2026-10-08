"""
Perfil del usuario, en lo mínimo: nombre y avatar, y los datos corporales
(fecha de nacimiento, altura, peso y peso objetivo) que sirven para estimar
calorías y ver el progreso del peso.

Una sola fuente de verdad para la web (views.profile_page) y la app móvil
(api.profile): catálogos del avatar, validación y datos derivados (edad,
IMC, kg hasta el objetivo). Se guarda en UserSettings; cada peso nuevo deja
una fila en WeightLog (historial). El cumplimiento (rachas, % semanal,
horas) NO vive aquí: ya está en Estadísticas.
"""
import datetime as _dt

from django.utils import timezone

DISPLAY_NAME_MAX = 40

AVATAR_EMOJIS = [
    "💪", "🏋️", "🏃", "🧗", "🤸", "🧘", "🚴", "🥇",
    "🔥", "⚡", "🚀", "🦁", "🐺", "🦅", "🐻", "🦊",
    "📚", "🎯", "🧠", "🌱", "☕", "🌙", "😎", "🤓",
]
AVATAR_COLORS = [
    "#FF6A1F",  # ember (el de la app)
    "#E5493A",
    "#F2A93B",
    "#4CAF7A",
    "#2FA6A0",
    "#4A8BDF",
    "#7C6CE0",
    "#C95FA8",
]
DEFAULT_EMOJI = AVATAR_EMOJIS[0]
DEFAULT_COLOR = AVATAR_COLORS[0]

HEIGHT_RANGE = (100, 250)
WEIGHT_RANGE = (30, 300)
MIN_BIRTH_YEAR = 1900

HISTORY_LIMIT = 8

# Campos que envía el formulario del perfil (web y app).
FORM_FIELDS = (
    "display_name", "avatar_emoji", "avatar_color",
    "birth_date", "height_cm", "body_weight_kg", "goal_weight_kg",
)


def get_settings(user):
    """UserSettings del usuario (sin guardar si todavía no existe)."""
    from .models import UserSettings
    us = UserSettings.objects.filter(user=user).first()
    return us or UserSettings(user=user)


def age_from(birth_date, today=None):
    if not birth_date:
        return None
    today = today or timezone.localdate()
    years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return max(years, 0)


def bmi_from(weight_kg, height_cm):
    if not weight_kg or not height_cm:
        return None
    return round(weight_kg / ((height_cm / 100) ** 2), 1)


def log_weight(user, kg, day=None):
    """Guarda el peso de hoy en el historial (uno por día; el último gana)."""
    from .models import WeightLog
    WeightLog.objects.update_or_create(
        user=user, date=day or timezone.localdate(), defaults={"weight_kg": float(kg)},
    )


def weight_history(user, limit=HISTORY_LIMIT):
    """Últimos pesos (más reciente primero) y el cambio respecto al anterior."""
    from .models import WeightLog
    rows = list(WeightLog.objects.filter(user=user).order_by("-date")[:limit + 1])
    entries = [{"date": r.date.isoformat(), "kg": round(r.weight_kg, 1)} for r in rows[:limit]]
    change = None
    if len(rows) >= 2:
        change = round(rows[0].weight_kg - rows[1].weight_kg, 1)
    return entries, change


def profile_data(user):
    """Perfil listo para pintar (web) o serializar (API)."""
    us = get_settings(user)
    name = (us.display_name or "").strip()
    history, change = weight_history(user) if user.pk else ([], None)
    weight = us.body_weight_kg
    goal = us.goal_weight_kg
    return {
        "display_name": name,
        "shown_name": name or "Tu nombre",
        "avatar_emoji": us.avatar_emoji or DEFAULT_EMOJI,
        "avatar_color": us.avatar_color or DEFAULT_COLOR,
        "birth_date": us.birth_date.isoformat() if us.birth_date else "",
        "age": age_from(us.birth_date),
        "height_cm": us.height_cm,
        "body_weight_kg": weight,
        "goal_weight_kg": goal,
        "bmi": bmi_from(weight, us.height_cm),
        # kg que faltan para el objetivo (negativo = queda por bajar).
        "to_goal_kg": round(goal - weight, 1) if (goal and weight) else None,
        "weight_history": history,
        "weight_change": change,
    }


def _to_float(raw):
    return float(str(raw).strip().replace(",", "."))


def apply_profile(user, data):
    """
    Valida `data` (dict con cualquiera de los campos del perfil) y guarda lo
    que venga. Solo toca las claves presentes; "" o None vacía el campo
    opcional. Devuelve (ok, errores): si hay algún error NO se guarda nada.
    """
    from .models import UserSettings
    changes, errors = {}, {}

    if "display_name" in data:
        name = " ".join(str(data.get("display_name") or "").split())
        if len(name) > DISPLAY_NAME_MAX:
            errors["display_name"] = f"Nombre: máximo {DISPLAY_NAME_MAX} caracteres."
        else:
            changes["display_name"] = name

    if "avatar_emoji" in data:
        emoji = str(data.get("avatar_emoji") or "").strip()
        if emoji and emoji not in AVATAR_EMOJIS:
            errors["avatar_emoji"] = "Emoji no válido."
        else:
            changes["avatar_emoji"] = emoji or DEFAULT_EMOJI

    if "avatar_color" in data:
        color = str(data.get("avatar_color") or "").strip().upper()
        if color and color not in AVATAR_COLORS:
            errors["avatar_color"] = "Color no válido."
        else:
            changes["avatar_color"] = color or DEFAULT_COLOR

    if "birth_date" in data:
        raw = data.get("birth_date")
        if raw is None or str(raw).strip() == "":
            changes["birth_date"] = None
        else:
            try:
                d = _dt.date.fromisoformat(str(raw).strip())
            except ValueError:
                errors["birth_date"] = "Fecha de nacimiento no válida."
            else:
                if d > timezone.localdate() or d.year < MIN_BIRTH_YEAR:
                    errors["birth_date"] = "La fecha de nacimiento no es posible."
                else:
                    changes["birth_date"] = d

    numeric = (
        ("height_cm", HEIGHT_RANGE, "La altura", "cm", True),
        ("body_weight_kg", WEIGHT_RANGE, "El peso", "kg", False),
        ("goal_weight_kg", WEIGHT_RANGE, "El peso objetivo", "kg", False),
    )
    for field, (lo, hi), label, unit, as_int in numeric:
        if field not in data:
            continue
        raw = data.get(field)
        if raw is None or str(raw).strip() == "":
            changes[field] = None
            continue
        try:
            value = _to_float(raw)
        except (TypeError, ValueError):
            errors[field] = f"{label}: pon un número válido."
            continue
        if not (lo <= value <= hi):
            errors[field] = f"{label} tiene que estar entre {lo} y {hi} {unit}."
            continue
        changes[field] = round(value) if as_int else value

    if errors:
        return False, errors
    if changes:
        previous = get_settings(user).body_weight_kg
        UserSettings.objects.update_or_create(user=user, defaults=changes)
        new_weight = changes.get("body_weight_kg")
        if new_weight is not None and new_weight != previous:
            log_weight(user, new_weight)
    return True, {}
