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
