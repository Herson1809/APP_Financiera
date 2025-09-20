from django.urls import re_path
from . import views

urlpatterns = [
    re_path(r"^reports/income/?$", views.income_report, name="income-report"),
]
