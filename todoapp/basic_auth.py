"""
Candado simple de usuario/contraseña para TODA la app.

Como es un to-do list de un solo usuario (tu), en vez de montar un
sistema de login completo (formularios, sesiones, registro...) usamos
HTTP Basic Auth: el navegador te muestra una ventana emergente pidiendo
usuario y contraseña antes de dejarte ver nada.

Se activa SOLO si defines las variables de entorno BASIC_AUTH_USER y
BASIC_AUTH_PASSWORD en el hosting. En local, si no las defines, el
candado queda desactivado (para no tener que loguearte cada vez que
programas).
"""
import base64

from django.conf import settings
from django.http import HttpResponse


class BasicAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si no has configurado usuario/contraseña, no se activa el candado.
        if not settings.BASIC_AUTH_USER or not settings.BASIC_AUTH_PASSWORD:
            return self.get_response(request)

        # El registro de depuración (botón 📋) lleva su propio token corto
        # en la URL/petición (settings.DEBUG_LOG_TOKEN, ver
        # tasks/api.py: debug_log_create/debug_log_latest) precisamente
        # para poder leerlo sin la contraseña real de la app -- así que
        # aquí NO se le exige además el candado general.
        if request.path.startswith("/api/debug-log/"):
            return self.get_response(request)

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            try:
                scheme, credentials = auth_header.split(" ", 1)
                if scheme.lower() == "basic":
                    decoded = base64.b64decode(credentials).decode("utf-8")
                    username, password = decoded.split(":", 1)
                    if username == settings.BASIC_AUTH_USER and password == settings.BASIC_AUTH_PASSWORD:
                        return self.get_response(request)
            except Exception:
                pass

        response = HttpResponse("Acceso restringido.", status=401)
        response["WWW-Authenticate"] = 'Basic realm="Mi libreta de tareas"'
        return response
