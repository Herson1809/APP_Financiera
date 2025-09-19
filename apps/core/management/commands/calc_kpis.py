from collections import defaultdict
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, F, FloatField
from apps.core.models import Company, Scenario, Period, RevenueDriver, ExpenseProjection, KPI

class Command(BaseCommand):
    help = "Calcula KPIs básicos (Ingresos, Gastos, EBITDA) por periodo para una empresa y escenario."

    def add_arguments(self, parser):
        parser.add_argument("company", type=str, help="Nombre de la compañía (ej. 'MiEmpresa')")
        parser.add_argument("scenario", type=str, help="Nombre del escenario (ej. 'Base')")

    def handle(self, company, scenario, **opts):
        try:
            c = Company.objects.get(name=company)
        except Company.DoesNotExist:
            raise CommandError(f"Company '{company}' no existe")

        try:
            s = Scenario.objects.get(company=c, name=scenario)
        except Scenario.DoesNotExist:
            raise CommandError(f"Scenario '{scenario}' no existe para '{company}'")

        # Ingresos: sum(price * units) por periodo
        rev_qs = (
            RevenueDriver.objects
            .filter(company=c, scenario=s)
            .values("period")
            .annotate(amount=Sum(F("price") * F("units"), output_field=FloatField()))
        )

        # Gastos: sum(value) por periodo
        exp_qs = (
            ExpenseProjection.objects
            .filter(company=c, scenario=s)
            .values("period")
            .annotate(amount=Sum("value"))
        )

        rev_map = defaultdict(float)
        for r in rev_qs:
            rev_map[r["period"]] = float(r["amount"] or 0.0)
            p = Period.objects.get(pk=r["period"])
            KPI.objects.update_or_create(
                company=c, scenario=s, period=p,
                name=f"Ingresos {p.year}-{p.month:02d}",
                defaults={"value": rev_map[r['period']], "unit": "USD"},
            )

        exp_map = defaultdict(float)
        for e in exp_qs:
            exp_map[e["period"]] = float(e["amount"] or 0.0)
            p = Period.objects.get(pk=e["period"])
            KPI.objects.update_or_create(
                company=c, scenario=s, period=p,
                name=f"Gastos {p.year}-{p.month:02d}",
                defaults={"value": exp_map[e['period']], "unit": "USD"},
            )

        # ebitda = Ingresos - Gastos
        for pid in set(list(rev_map.keys()) + list(exp_map.keys())):
            p = Period.objects.get(pk=pid)
            ebitda = rev_map[pid] - exp_map[pid]
            KPI.objects.update_or_create(
                company=c, scenario=s, period=p,
                name=f"Resultado operativo {p.year}-{p.month:02d}",
                defaults={"value": ebitda, "unit": "USD"},
            )

        self.stdout.write(self.style.SUCCESS(f"KPIs recalculados para '{company}' / '{scenario}'"))



