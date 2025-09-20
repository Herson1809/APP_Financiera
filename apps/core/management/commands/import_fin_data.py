# apps/core/management/import_fin_data.py

import re
from decimal import Decimal
from pathlib import Path
import csv

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import connection, IntegrityError, transaction, models


REQUIRED_SCHEMAS = {
    "companies.csv": ["company_code", "company_name", "currency", "is_active"],
    "accounts.csv": ["account_code", "account_name", "account_type", "parent_code", "level", "is_leaf"],
    "cost_centers.csv": ["center_code", "center_name", "parent_code", "level", "is_active"],
    "periods.csv": ["period_code", "year", "month", "start_date", "end_date", "is_open"],
    "scenarios.csv": ["scenario_code", "scenario_name", "kind"],
    "facts_finance.csv": ["company_code", "period_code", "account_code", "center_code", "scenario_code", "amount"],
    "kpis.csv": ["kpi_code", "kpi_name", "formula", "unit", "sign", "direction"],
    "kpi_targets.csv": ["kpi_code", "period_code", "target_value", "lower_bound", "upper_bound"],
    "kpi_framework_links.csv": ["kpi_code", "framework_slug", "section_slug", "rationale"],
    "drivers.csv": ["driver_code", "driver_name", "category", "unit"],
    "projections_input.csv": ["company_code", "year", "driver_code", "driver_name", "assumption", "value", "note"],
}


# --- util lectura csv ---------------------------------------------------------

def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")
    except Exception as e:
        raise CommandError(f"Error leyendo {path.name}: {e}")


# --- helpers ORM seguros ------------------------------------------------------

def has_field(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields() if isinstance(f, models.Field))


def set_if_exists(obj, **field_values):
    for k, v in field_values.items():
        if has_field(obj.__class__, k):
            setattr(obj, k, v)


def parse_period_code(code: str) -> tuple[int, int]:
    """
    Acepta formatos:
      - '202401', '2024-01', '2024/01', '2024_01', '2024 01'
    """
    if not code:
        raise ValueError("period_code vacío")
    m = re.search(r"(\d{4})\D?(\d{1,2})", str(code))
    if not m:
        raise ValueError(f"period_code inválido: {code!r}")
    y = int(m.group(1)); mth = int(m.group(2))
    if not (1 <= mth <= 12):
        raise ValueError(f"Mes inválido en period_code: {code!r}")
    return y, mth


# --- ensure_* (crean o devuelven) --------------------------------------------

def ensure_company(company_code: str):
    Company = apps.get_model("core", "Company")
    obj = Company.objects.filter(name=company_code).first()  # usamos 'name' como llave natural
    if obj:
        return obj
    obj = Company()
    set_if_exists(obj, name=company_code, code=company_code, is_active=True)
    obj.save()
    return obj


def ensure_period(period_code: str):
    Period = apps.get_model("core", "Period")
    year, month = parse_period_code(period_code)
    obj, _ = Period.objects.get_or_create(year=year, month=month)
    return obj


def ensure_scenario(scenario_code: str, company):
    """
    En tu modelo Scenario ya vimos que suele llevar company y name.
    Creamos por (company, name).
    """
    Scenario = apps.get_model("core", "Scenario")
    obj, _ = Scenario.objects.get_or_create(company=company, name=scenario_code)
    return obj


def ensure_cost_center(center_code: str):
    """Si tu FactFinance no usa centro, igual lo creamos por si más adelante hace falta."""
    CostCenter = apps.get_model("core", "CostCenter")
    obj = CostCenter.objects.filter(name=center_code).first()
    if obj:
        return obj
    obj = CostCenter()
    set_if_exists(obj, name=center_code, code=center_code, level=1, is_active=True)
    obj.save()
    return obj


# --- account type helpers -----------------------------------------------------

# Si más adelante usas otro mapeo, ajusta aquí
def guess_account_type(account_code: str) -> str:
    n = (account_code or "").lower()
    if "ven" in n or "rev" in n:  # ventas / revenue
        return "REVENUE"
    if "cog" in n or "cost" in n or "compra" in n:
        return "COGS"
    if "depr" in n or "amort" in n:
        return "DEPR"
    if "fin" in n or "int" in n:
        return "FIN"
    if "tax" in n or "imp" in n:
        return "TAX"
    return "OPEX"


def ensure_account(account_code: str, acc_type: str):
    """
    Evita el problema de NOT NULL en core_account.level:
    - Si existe por ORM, usamos y rellenamos account_type si falta.
    - Si NO existe, insertamos por SQL crudo con 'level'=1 y luego traemos la instancia por ORM.
    """
    Account = apps.get_model("core", "Account")

    # ¿ya existe?
    a = Account.objects.filter(name=account_code).first()
    if a:
        if not getattr(a, "account_type", None):
            a.account_type = acc_type
            a.save(update_fields=["account_type"])
        return a

    # crear con SQL para evitar constraints ocultas (p.ej. 'level' NOT NULL)
    with connection.cursor() as cur:
        # Usamos INSERT OR IGNORE para que sea idempotente
        try:
            cur.execute(
                "INSERT OR IGNORE INTO core_account (name, account_type, level) VALUES (?,?,?)",
                [account_code, acc_type, 1],
            )
        except Exception:
            # Si tu tabla NO tiene 'level', probamos sin esa columna
            cur.execute(
                "INSERT OR IGNORE INTO core_account (name, account_type) VALUES (?,?)",
                [account_code, acc_type],
            )
        # Recuperar id
        cur.execute("SELECT id FROM core_account WHERE name = ?", [account_code])
        acc_id = cur.fetchone()[0]

    return Account.objects.get(pk=acc_id)


# --- importador de facts_finance.csv -----------------------------------------

def import_facts(base_dir: Path, stdout, stderr):
    """
    Lee import_data/templates/facts_finance.csv y escribe en core_factfinance:
      - company: por company_code (se usa como 'name')
      - period: por period_code -> (year, month)
      - account: por account_code (se usa como 'name'), con guess de account_type
      - scenario: por scenario_code (name) ligado a company
    """
    Fact = apps.get_model("core", "FactFinance")
    fpath = base_dir / "facts_finance.csv"
    if not fpath.exists():
        stdout.write("No se encontró facts_finance.csv; nada que importar en hechos.")
        return {"rows": 0, "ins": 0, "upd": 0, "err": 0}

    rows = ins = upd = err = 0

    # abrimos tolerando BOM
    with open(fpath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        with transaction.atomic():
            for row in reader:
                rows += 1
                try:
                    company_code = (row.get("company_code") or "").strip()
                    period_code = (row.get("period_code") or "").strip()
                    account_code = (row.get("account_code") or "").strip()
                    scenario_code = (row.get("scenario_code") or "").strip()
                    amount_raw = row.get("amount")

                    if not (company_code and period_code and account_code and scenario_code):
                        raise ValueError("Faltan campos obligatorios en la fila")

                    c = ensure_company(company_code)
                    p = ensure_period(period_code)
                    s = ensure_scenario(scenario_code, c)

                    acc_type = guess_account_type(account_code)
                    a = ensure_account(account_code, acc_type)

                    amt = Decimal(str(amount_raw).replace(",", "").strip())

                    obj, created = Fact.objects.update_or_create(
                        company=c, scenario=s, period=p, account=a,
                        defaults={"amount": amt},
                    )
                    if created:
                        ins += 1
                    else:
                        upd += 1
                except Exception as e:
                    err += 1
                    stderr.write(f"Fila {rows} ERROR -> {e}")

    stdout.write(f"RESUMEN → filas:{rows}, insertadas:{ins}, actualizadas:{upd}, errores:{err}")
    return {"rows": rows, "ins": ins, "upd": upd, "err": err}


# --- management command -------------------------------------------------------

class Command(BaseCommand):
    help = "Valida y (si no usas --dry-run) importa CSV normalizados de import_data/templates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-dir",
            default="import_data/templates",
            help="Carpeta con los CSV normalizados (por defecto: import_data/templates)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo valida estructura y muestra conteos; no escribe en BD",
        )

    def handle(self, *args, **opts):
        base_dir = Path(opts["base_dir"])
        if not base_dir.is_absolute():
            base_dir = Path(settings.BASE_DIR) / base_dir
        if not base_dir.exists():
            raise CommandError(f"Carpeta no encontrada: {base_dir}")

        self.stdout.write(self.style.HTTP_INFO(f"Base dir: {base_dir}"))
        total_rows, problems = 0, []

        # 1) Validación de estructura (todos los archivos requeridos y columnas)
        for fname, required_cols in REQUIRED_SCHEMAS.items():
            fpath = base_dir / fname
            if not fpath.exists():
                problems.append(f"Falta archivo: {fname}")
                continue
            df = read_csv(fpath)
            cols = list(map(str, df.columns))
            missing = [c for c in required_cols if c not in cols]
            if missing:
                problems.append(f"{fname}: faltan columnas {missing} | columnas encontradas={cols}")
            self.stdout.write(f"✔ {fname:22s} filas={len(df):6d} cols={len(cols):2d}")
            total_rows += len(df)

        if problems:
            self.stdout.write("")
            for p in problems:
                self.stderr.write(self.style.ERROR(f"- {p}"))
            raise CommandError("Validación con errores. Corrige antes de importar.")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nEstructura OK. Archivos validados: {len(REQUIRED_SCHEMAS)}. Filas totales: {total_rows}"
            )
        )

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY-RUN activado: no se escribieron datos."))
            return

        # 2) Importación real (por fases; de momento, hechos financieros)
        self.stdout.write(self.style.HTTP_INFO("\nImportando hechos financieros (facts_finance.csv)..."))
        summary = import_facts(base_dir, self.stdout, self.stderr)

        self.stdout.write(self.style.SUCCESS("\nImportación finalizada."))
        self.stdout.write(f"Hechos → {summary}")

