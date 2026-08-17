from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from tasks.views import mobile_apk_download

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('tasks.api_urls')),
    path('tareas/', include('tasks.urls')),
    # Fuera de /api/ a propósito: no es un endpoint JSON, y así CORS
    # (que solo aplica bajo /api/, ver settings.CORS_URLS_REGEX) no le
    # afecta — la descarga la abre el navegador del sistema, no fetch.
    path('mobile/apk/', mobile_apk_download, name='mobile_apk_download'),
    path('', RedirectView.as_view(pattern_name='tasks:task_list', permanent=False)),
]
