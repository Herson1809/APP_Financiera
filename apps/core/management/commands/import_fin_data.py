import sys
from pathlib import Path
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

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

def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")
    except Exception as e:
        raise CommandError(f"Error leyendo {path.name}: {e}")

class Command(BaseCommand):
    help = "Valida e (en el siguiente paso) importará CSV normalizados de import_data/templates"

    def add_arguments(self, parser):
        parser.add_argument("--base-dir", default="import_data/templates",
            help="Carpeta con los CSV normalizados (por defecto: import_data/templates)")
        parser.add_argument("--dry-run", action="store_true",
            help="Solo valida estructura y muestra conteos; no escribe en BD")

    def handle(self, *args, **opts):
        base_dir = Path(opts["base_dir"])
        if not base_dir.is_absolute():
            base_dir = Path(settings.BASE_DIR) / base_dir
        if not base_dir.exists():
            raise CommandError(f"Carpeta no encontrada: {base_dir}")

        self.stdout.write(self.style.HTTP_INFO(f"Base dir: {base_dir}"))
        total_rows, problems = 0, []

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

        self.stdout.write(self.style.SUCCESS(
            f"\nEstructura OK. Archivos validados: {len(REQUIRED_SCHEMAS)}. Filas totales: {total_rows}"
        ))
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY-RUN activado: no se escribieron datos."))
            return

        self.stdout.write(self.style.WARNING("Importación real aún no implementada en este paso."))
