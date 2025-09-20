# apps/core/urls.py
from django.urls import path, re_path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("foundation/", views.foundation, name="foundation"),

    # Estado de Resultados (con y sin "/")
    re_path(r"^reports/income/?$", views.income_report, name="income-report"),
]
