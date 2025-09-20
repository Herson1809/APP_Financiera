from django.urls import re_path
from . import views

urlpatterns = [
    # otras rutas que ya tengas…
    re_path(r"^reports/income/?$", views.income_report, name="income-report"),
]
