from django import template

from .. import profile
from ..utils import get_current_user

register = template.Library()


@register.simple_tag
def nav_profile():
    """Avatar del usuario para el icono de perfil de la barra de navegación."""
    try:
        return profile.profile_data(get_current_user())
    except Exception:
        # Una barra de navegación nunca debe tumbar la página.
        return {"avatar_emoji": profile.DEFAULT_EMOJI, "avatar_color": profile.DEFAULT_COLOR, "shown_name": "Perfil"}
