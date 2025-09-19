import csv
from pathlib import Path
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection, IntegrityError

from apps.core.models import (
    Company, Account, CostCenter, Period, Scenario, FactFinance
)

# -------------------- Utilidades --------------------

def _read_csv_rows(csv_path: Path):
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append({(k or "").strip(): (v or "").strip() for k, v in r.items()})
        return rows

def _first(row, *keys, default=""):
    for k in keys:
        if k in row and str(row[k]).strip() != "":
            return row[k].strip()
    return default

def _to_int(val, default=0):
    try:
        return int(str(val).strip())
    except Exception:
        try:
            return int(float(str(val).strip()))
        except Exception:
            return default

def _to_decimal(val, default=Decimal("0")):
    s = str(val or "").strip().replace(",", "")
    if s == "":
        return default
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        try:
            return Decimal(str(float(s)))
        except Exception:
            return default

def _db_table_info(table_name: str):
    with connection.cursor() as cur:
        inner = getattr(cur, "cursor", cur)
        inner.execute(f"PRAGMA table_info({table_name});")
        out = {}
        for cid, name, ctype, notnull, dflt, pk in inner.fetchall():
            out[name] = (bool(notnull), dflt)
        return out

# -------------------- Comando --------------------

class Command(BaseCommand):
    help = "Aplica plantillas desde --base-dir para poblar catálogos y hechos (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-dir",
            dest="base_dir",
            default="import_data/templates",
            help="Directorio base de plantillas CSV (por defecto: import_data/templates)",
        )

    def handle(self, *args, **options):
        base_dir = Path(options["base_dir"]).resolve()
        self.stdout.write(self.style.NOTICE(f"Usando base-dir: {base_dir}"))
        if not base_dir.exists():
            raise CommandError(f"No existe el directorio: {base_dir}")

        rows_companies = _read_csv_rows(base_dir / "companies.csv")
        rows_accounts  = _read_csv_rows(base_dir / "accounts.csv")
        rows_centers   = _read_csv_rows(base_dir / "centers.csv")     # si no tienes centers.csv, queda vacío (no falla)
        rows_periods   = _read_csv_rows(base_dir / "periods.csv")
        rows_scen      = _read_csv_rows(base_dir / "scenarios.csv")
        rows_facts     = _read_csv_rows(base_dir / "facts_finance.csv")

        summary = {
            "companies": {"created": 0, "updated": 0, "skipped": 0},
            "accounts":  {"created": 0, "updated": 0, "skipped": 0},
            "centers":   {"created": 0, "updated": 0, "skipped": 0},
            "periods":   {"created": 0, "updated": 0, "skipped": 0},
            "scenarios": {"created": 0, "updated": 0, "skipped": 0},
            "facts":     {"created": 0, "updated": 0, "skipped": 0},
        }

        with transaction.atomic():
            self._import_companies(rows_companies, summary["companies"])
            self._import_accounts(rows_accounts, summary["accounts"])
            self._import_centers(rows_centers, summary["centers"])
            self._import_periods(rows_periods, summary["periods"])
            self._import_scenarios(rows_scen, summary["scenarios"])
            self._import_facts_finance(rows_facts, summary["facts"])

        self.stdout.write(self.style.SUCCESS("Importación completada."))
        for k, v in summary.items():
            self.stdout.write(f"  {k}: {v}")

    # -------------------- Importadores --------------------

    @transaction.atomic
    def _import_companies(self, rows, counters):
        self.stdout.write(self.style.NOTICE(f"Importando companies ({len(rows)} filas)..."))
        for r in rows:
            code = _first(r, "code", "company_code")
            name = _first(r, "name", "company_name", default=code or "Confort.com")
            if not code:
                counters["skipped"] += 1
                continue
            obj, created = Company.objects.update_or_create(
                code=code, defaults={"name": name}
            )
            counters["created" if created else "updated"] += 1

    def _raw_insert_account_if_needed(self, code, name, acc_type):
        with connection.cursor() as cur:
            inner = getattr(cur, "cursor", cur)   # ¡usar SIEMPRE inner!
            cols_info = _db_table_info("core_account")
            columns = ["code", "name", "account_type"]
            params = [code, name, acc_type]
            if "level" in cols_info:
                columns.append("level"); params.append(1)
            if "is_leaf" in cols_info:
                columns.append("is_leaf"); params.append(1)
            placeholders = ",".join(["?"] * len(columns))
            sql = f"INSERT OR IGNORE INTO core_account ({','.join(columns)}) VALUES ({placeholders})"
            inner.execute(sql, params)

    @transaction.atomic
    def _import_accounts(self, rows, counters):
        self.stdout.write(self.style.NOTICE(f"Importando accounts ({len(rows)} filas)..."))

        model_fields = {f.name for f in Account._meta.get_fields()}
        have_level   = "level" in model_fields
        have_is_leaf = "is_leaf" in model_fields
        have_parent  = "parent" in model_fields

        cols_info = _db_table_info("core_account")
        db_requires_level   = ("level"   in cols_info and cols_info["level"][0]   and cols_info["level"][1]   is None and not have_level)
        db_requires_is_leaf = ("is_leaf" in cols_info and cols_info["is_leaf"][0] and cols_info["is_leaf"][1] is None and not have_is_leaf)

        cache = {a.code: a for a in Account.objects.all().only("id", "code", "name")}

        def to_bool(v):
            s = str(v or "").strip().lower()
            if s == "":
                return True
            return s in ("1", "true", "t", "yes", "y", "si", "sí")

        for r in rows:
            code = _first(r, "code", "account_code")
            name = _first(r, "name", "account_name", default=code)
            acc_type = _first(r, "account_type", "type", default="Expense")
            parent_code = _first(r, "parent_code")
            level = _to_int(_first(r, "level"), default=1)
            is_leaf = to_bool(_first(r, "is_leaf", default="1"))

            if not code:
                counters["skipped"] += 1
                continue

            obj = cache.get(code)
            if obj:
                changed = False
                updates = []
                if obj.name != name:
                    obj.name = name; updates.append("name"); changed = True
                if getattr(obj, "account_type", None) != acc_type:
                    obj.account_type = acc_type; updates.append("account_type"); changed = True
                if have_level and getattr(obj, "level", None) != level:
                    obj.level = level; updates.append("level"); changed = True
                if have_is_leaf and getattr(obj, "is_leaf", None) != is_leaf:
                    obj.is_leaf = is_leaf; updates.append("is_leaf"); changed = True
                if have_parent and parent_code:
                    try:
                        parent = Account.objects.get(code=parent_code)
                    except Account.DoesNotExist:
                        parent = None
                    if obj.parent_id != (parent.id if parent else None):
                        obj.parent = parent; updates.append("parent"); changed = True
                if changed:
                    obj.save(update_fields=updates)
                    counters["updated"] += 1
                else:
                    counters["skipped"] += 1
                continue

            if (db_requires_level or db_requires_is_leaf) and (not have_level or not have_is_leaf):
                self._raw_insert_account_if_needed(code, name, acc_type)
                obj = Account.objects.get(code=code)
                counters["created"] += 1
                cache[code] = obj
                continue

            defaults = {"name": name, "account_type": acc_type}
            if have_level:   defaults["level"]   = level
            if have_is_leaf: defaults["is_leaf"] = is_leaf
            if have_parent and parent_code:
                try:
                    defaults["parent"] = Account.objects.get(code=parent_code)
                except Account.DoesNotExist:
                    pass

            obj = Account.objects.create(code=code, **defaults)
            counters["created"] += 1
            cache[code] = obj

    @transaction.atomic
    def _import_centers(self, rows, counters):
        self.stdout.write(self.style.NOTICE(f"Importando centers ({len(rows)} filas)..."))
        for r in rows:
            code = _first(r, "code", "center_code", "cost_center")
            name = _first(r, "name", "center_name", default=code)
            if not code:
                counters["skipped"] += 1
                continue
            obj, created = CostCenter.objects.update_or_create(
                code=code, defaults={"name": name}
            )
            counters["created" if created else "updated"] += 1

    @transaction.atomic
    def _import_periods(self, rows, counters):
        self.stdout.write(self.style.NOTICE(f"Importando periods ({len(rows)} filas)..."))
        for r in rows:
            year = _to_int(_first(r, "year"), default=0)
            month = _to_int(_first(r, "month"), default=0)
            if year <= 0:
                counters["skipped"] += 1
                continue
            if month <= 0:
                month = 12
            obj, created = Period.objects.update_or_create(year=year, month=month)
            counters["created" if created else "updated"] += 1

    @transaction.atomic
    def _import_scenarios(self, rows, counters):
        self.stdout.write(self.style.NOTICE(f"Importando scenarios ({len(rows)} filas)..."))
        companies = {c.code: c for c in Company.objects.all().only("id", "code")}
        companies_by_name = {c.name: c for c in Company.objects.all().only("id", "name")}
        for r in rows:
            company_code = _first(r, "company_code")
            company_name = _first(r, "company_name")
            name = _first(r, "name", "scenario", "scenario_name", default="Base")
            company = companies.get(company_code) or companies_by_name.get(company_name)
            if not company:
                company, _ = Company.objects.get_or_create(code="Confort.com", defaults={"name": "Confort.com"})
            obj, created = Scenario.objects.update_or_create(name=name, defaults={"company": company})
            counters["created" if created else "updated"] += 1

    @transaction.atomic
    def _import_facts_finance(self, rows, counters):
        self.stdout.write(self.style.NOTICE(f"Importando facts_finance ({len(rows)} filas)..."))
        companies = {c.code: c for c in Company.objects.all().only("id", "code")}
        companies_by_name = {c.name: c for c in Company.objects.all().only("id", "name")}
        accounts = {a.code: a for a in Account.objects.all().only("id", "code")}
        centers  = {cc.code: cc for cc in CostCenter.objects.all().only("id", "code")}
        for r in rows:
            company_code = _first(r, "company_code")
            company_name = _first(r, "company_name")
            scenario_name = _first(r, "scenario", "scenario_name", "scenario_code", default="Base")
            year  = _to_int(_first(r, "year"), default=0)
            month = _to_int(_first(r, "month"), default=12)
            account_code = _first(r, "account_code", "code")
            account_name = _first(r, "account_name", "name", default=account_code)
            center_code  = _first(r, "cost_center", "center_code")
            amount       = _to_decimal(_first(r, "amount"), default=Decimal("0"))

            if year <= 0 or not account_code:
                counters["skipped"] += 1
                continue

            company = companies.get(company_code) or companies_by_name.get(company_name)
            if not company:
                company, _ = Company.objects.get_or_create(code="Confort.com", defaults={"name": "Confort.com"})
                companies[company.code] = company

            scenario, _ = Scenario.objects.get_or_create(name=scenario_name, defaults={"company": company})
            period, _ = Period.objects.get_or_create(year=year, month=month)

            account = accounts.get(account_code)
            if not account:
                try:
                    account = Account.objects.create(code=account_code, name=account_name or account_code, account_type="Expense")
                except IntegrityError:
                    self._raw_insert_account_if_needed(account_code, account_name or account_code, "Expense")
                    account = Account.objects.get(code=account_code)
                accounts[account_code] = account

            center = None
            if center_code:
                center = centers.get(center_code)
                if not center:
                    center = CostCenter.objects.create(code=center_code, name=center_code)
                    centers[center_code] = center

            obj, created = FactFinance.objects.update_or_create(
                company=company,
                scenario=scenario,
                period=period,
                account=account,
                center=center,
                defaults={"amount": amount},
            )
            counters["created" if created else "updated"] += 1
