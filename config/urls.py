from django.contrib import admin
from django.urls import path
from apps.core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Conectar tus plantillas existentes (SIN crear archivos nuevos)
    path('', core_views.home, name='home'),                 # templates/core/home.html
    path('foundation/', core_views.foundation, name='foundation'),  # templates/core/dashboard.html

    # EERR (ya existente)
    path('reports/income', core_views.income_report, name='income-report'),
]
