# apps/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # con slash y sin slash (para evitar confusiones)
    path("reports/income/", views.income_report, name="income_report"),
    path("reports/income",  views.income_report),
]
