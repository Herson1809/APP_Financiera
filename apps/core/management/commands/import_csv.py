import csv
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core.models import Company, Scenario, Period, Assumption, RevenueDriver, ExpenseProjection, DebtInstrument

def get_period(iso: str):
    try:
        year, month = iso.split("-")
        p, _ = Period.objects.get_or_create(year=int(year), month=int(month))
        return p
    except Exception as e:
        raise CommandError(f"Periodo inválido '{iso}': {e}")

class Command(BaseCommand):
    help = "Importa CSV: assumptions | revenue_drivers | expenses | debt_instruments"

    def add_arguments(self, parser):
        parser.add_argument("dataset", type=str)
        parser.add_argument("csv_path", type=str)

    @transaction.atomic
    def handle(self, *args, **opts):
        ds = opts["dataset"]
        path = Path(opts["csv_path"])
        if not path.exists():
            raise CommandError(f"No existe {path}")

        with path.open(newline="", encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            if ds == "assumptions":
                for row in r:
                    company, _ = Company.objects.get_or_create(name=row["company"])
                    scenario, _ = Scenario.objects.get_or_create(company=company, name=row["scenario"])
                    period = get_period(row["period"])
                    Assumption.objects.update_or_create(
                        company=company, scenario=scenario, period=period, key=row["key"],
                        defaults=dict(value=float(row["value"]), unit=row.get("unit","ratio"), notes=row.get("notes",""))
                    )
            elif ds == "revenue_drivers":
                for row in r:
                    company, _ = Company.objects.get_or_create(name=row["company"])
                    scenario, _ = Scenario.objects.get_or_create(company=company, name=row["scenario"])
                    period = get_period(row["period"])
                    RevenueDriver.objects.create(
                        company=company, scenario=scenario, period=period,
                        product=row.get("product") or "General",
                        price=float(row["price"]), units=float(row["units"]),
                        currency=row.get("currency","USD"), notes=row.get("notes","")
                    )
            elif ds == "expenses":
                for row in r:
                    company, _ = Company.objects.get_or_create(name=row["company"])
                    scenario, _ = Scenario.objects.get_or_create(company=company, name=row["scenario"])
                    period = get_period(row["period"])
                    ExpenseProjection.objects.create(
                        company=company, scenario=scenario, period=period,
                        line_item_code=row["line_item_code"], line_item_name=row["line_item_name"],
                        driver_type=row["driver_type"], value=float(row["value"]),
                        currency=row.get("currency","USD"), notes=row.get("notes","")
                    )
            elif ds == "debt_instruments":
                for row in r:
                    company, _ = Company.objects.get_or_create(name=row["company"])
                    DebtInstrument.objects.create(
                        company=company, name=row["name"], principal=float(row["principal"]),
                        rate_annual=float(row["rate_annual"]), term_months=int(row["term_months"]),
                        start_date=row["start_date"], payment_frequency=row.get("payment_frequency","monthly"),
                        currency=row.get("currency","USD"), notes=row.get("notes","")
                    )
            else:
                raise CommandError("Dataset no soportado: usa assumptions | revenue_drivers | expenses | debt_instruments")

        self.stdout.write(self.style.SUCCESS(f"Importación '{ds}' OK desde {path}"))

