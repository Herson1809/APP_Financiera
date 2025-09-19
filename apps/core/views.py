# apps/core/views.py
from django.shortcuts import render, redirect
from django.db.models import Sum
from .models import Company, Scenario, FactFinance

def _pick_defaults():
    """
    Devuelve (company, scenario) razonables sin romperse si cambian los datos.
    Intenta Confort.com/Base y si no, toma el primero que exista.
    """
    company = Company.objects.filter(code="Confort.com").first() or Company.objects.order_by("id").first()
    scenario = Scenario.objects.filter(name="Base").first() or Scenario.objects.order_by("id").first()
    return company, scenario

# ====== VISTAS QUE USAN TUS TEMPLATES EXISTENTES ======

def home(request):
    # Usa tu archivo existente: templates/core/home.html
    return render(request, "core/home.html", {})

def foundation(request):
    # Usa tu archivo existente: templates/core/dashboard.html
    return render(request, "core/dashboard.html", {})

# ====== EERR (tal como lo tenías, solo renderiza reports/income.html) ======

def income_report(request):
    """
    Mini Estado de Resultados.
    - Si no viene ?year=YYYY redirige al último año disponible.
    - Suma por cuenta y calcula totales simples por prefijo (4=ingresos, 5=gastos).
    Renderiza reports/income.html (extiende base con sidebar).
    """
    company, scenario = _pick_defaults()
    if not company or not scenario:
        return render(request, "reports/income.html", {
            "company": company,
            "scenario": scenario,
            "year": None,
            "last_year": None,
            "rows": [],
            "total_ingresos": 0,
            "total_gastos": 0,
            "utilidad": 0,
            "msg": "Faltan datos de empresa o escenario."
        })

    base_qs = FactFinance.objects.filter(company=company, scenario=scenario)

    year_param = request.GET.get("year")
    if not year_param:
        last_year = (
            base_qs.order_by("-period__year")
                   .values_list("period__year", flat=True)
                   .first()
        )
        if last_year:
            return redirect(f"{request.path}?year={last_year}")
        return render(request, "reports/income.html", {
            "company": company,
            "scenario": scenario,
            "year": None,
            "last_year": None,
            "rows": [],
            "total_ingresos": 0,
            "total_gastos": 0,
            "utilidad": 0,
            "msg": "No hay datos para mostrar todavía."
        })

    try:
        year = int(year_param)
    except ValueError:
        return redirect(request.path)

    last_year = (
        base_qs.order_by("-period__year")
               .values_list("period__year", flat=True)
               .first()
    )

    qs = base_qs.filter(period__year=year)

    rows = (
        qs.values("account__code", "account__name")
          .annotate(total=Sum("amount"))
          .order_by("account__code")
    )

    total_ingresos = sum((r["total"] or 0) for r in rows if str(r["account__code"]).startswith("4"))
    total_gastos   = sum((r["total"] or 0) for r in rows if str(r["account__code"]).startswith("5"))
    utilidad       = (total_ingresos or 0) - (total_gastos or 0)

    context = {
        "company": company,
        "scenario": scenario,
        "year": year,
        "last_year": last_year,
        "rows": rows,
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "utilidad": utilidad,
        "msg": None,
    }
    return render(request, "reports/income.html", context)
