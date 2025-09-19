import re
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

# ===================== Utilidades =====================

SPAN_MONTHS = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "set": 9, "sept": 9, "septiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}
ENG_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
MONTH_LOOKUP = {**SPAN_MONTHS, **ENG_MONTHS}

EXPECTED_HEADERS = {
    "empresa","periodo","cuenta","monto","centro","escenario",
    "mes","año","anio","year","month","saldo","valor"
}

def slugify(s: str) -> str:
    s = str(s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")[:64]

def _norm(x: str) -> str:
    return re.sub(r"\s+", "", str(x).strip().lower())

def is_floaty(x) -> bool:
    try:
        float(str(x).replace(",", ""))
        return True
    except Exception:
        return False

def score_period(val: str) -> int:
    v = str(val or "").strip()
    if re.match(r"^\d{4}[-/](0?[1-9]|1[0-2])$", v):
        return 3
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            datetime.strptime(v, fmt)
            return 2
        except Exception:
            pass
    if re.search(r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|jan|aug|dec|month)", v, re.I):
        return 1
    return 0

def build_period_code(row: dict, period_col: str | None, default_period: str) -> str:
    if not period_col:
        return default_period
    v = str(row.get(period_col, "")).strip()
    if re.match(r"^\d{4}[-/](0?[1-9]|1[0-2])$", v):
        y, m = re.split(r"[-/]", v)
        return f"{int(y):04d}-{int(m):02d}"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            d = datetime.strptime(v, fmt)
            return f"{d.year:04d}-{d.month:02d}"
        except Exception:
            pass
    return default_period

def choose_header_row(df: pd.DataFrame, max_scan: int = 10) -> int | None:
    n = min(max_scan, len(df))
    best_row, best_score = None, -1
    for i in range(n):
        row = [_norm(v) for v in df.iloc[i].tolist()]
        score = sum(1 for v in row if v in EXPECTED_HEADERS)
        if score > best_score:
            best_score, best_row = score, i
    return best_row if best_score >= 3 else None

def normalize_headers(cols):
    out, seen = [], {}
    for i, c in enumerate(cols):
        name = str(c).strip()
        if not name or name.lower() in ("nan","none","null") or name.startswith("Unnamed"):
            name = f"col_{i+1}"
        key = name
        if key in seen:
            seen[key] += 1
            name = f"{name}_{seen[key]}"
        else:
            seen[key] = 1
        out.append(name)
    return out

def match_col(df: pd.DataFrame, target: str) -> str | None:
    ntarget = _norm(target)
    for c in df.columns:
        if _norm(c) == ntarget:
            return c
    return None

def guess_columns(df: pd.DataFrame) -> dict:
    sample = df.head(100)
    scores_num = {c: sample[c].apply(is_floaty).mean() for c in df.columns}
    scores_period = {c: sample[c].apply(score_period).mean() for c in df.columns}

    amount_col = max(scores_num, key=scores_num.get) if scores_num else None
    if scores_num.get(amount_col, 0) < 0.6:
        amount_col = None

    period_col = max(scores_period, key=scores_period.get) if scores_period else None
    if scores_period.get(period_col, 0) < 0.6:
        period_col = None

    company_col = None
    for c in df.columns:
        vals = sample[c].dropna().astype(str).str.strip()
        uniq = vals.nunique()
        if 0 < uniq <= 3 and vals.apply(lambda s: not is_floaty(s)).mean() > 0.9:
            company_col = c
            break

    account_col = None
    for c in df.columns:
        if c == company_col: 
            continue
        vals = sample[c].dropna().astype(str).str.strip()
        if vals.apply(lambda s: not is_floaty(s)).mean() > 0.9 and vals.nunique() >= 10:
            account_col = c
            break

    center_col = None
    scenario_col = None
    for c in df.columns:
        if c in {company_col, period_col, amount_col, account_col}:
            continue
        vals = sample[c].dropna().astype(str).str.strip()
        uniq = vals.nunique()
        if center_col is None and 3 <= uniq <= 50:
            center_col = c
        if scenario_col is None and 1 <= uniq <= 5:
            scenario_col = c

    return {
        "Empresa": company_col, "Periodo": period_col, "Cuenta": account_col,
        "Monto": amount_col, "Centro": center_col, "Escenario": scenario_col,
    }

def _month_from_token(tok: str) -> int | None:
    t = _norm(tok)
    if t in MONTH_LOOKUP:
        return MONTH_LOOKUP[t]
    if re.fullmatch(r"(0?[1-9]|1[0-2])", t):
        return int(t)
    if re.fullmatch(r"m(0?[1-9]|1[0-2])", t):
        return int(t[1:])
    return None

def period_from_header(col: str, default_year: int | None) -> str | None:
    c = str(col).strip().lower()
    m = re.match(r"^(\d{4})[-/](0?[1-9]|1[0-2])$", c)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m = re.search(r"(?:(\d{4})\D*)?([a-z]{3,9}|0?[1-2]?\d)", c)
    if m:
        y = m.group(1)
        token = m.group(2)
        mm = _month_from_token(token)
        if mm:
            year = int(y) if y else (int(default_year) if default_year else None)
            if year:
                return f"{year:04d}-{mm:02d}"
    return None

def detect_month_columns(df: pd.DataFrame, default_year: int | None):
    mapping = {}
    for col in df.columns:
        p = period_from_header(col, default_year)
        if p:
            mapping[col] = p
    if len(mapping) >= 6:
        return mapping
    return {}

# ===================== Comando =====================

class Command(BaseCommand):
    help = "Mapea CSV de import_data/raw hacia plantillas normalizadas en import_data/templates (wide→long mensual)."

    def add_arguments(self, parser):
        parser.add_argument("--raw-dir", default="import_data/raw", help="Carpeta de entrada RAW")
        parser.add_argument("--out-dir", default="import_data/templates", help="Carpeta de salida TEMPLATES")
        parser.add_argument("--map", default="import_data/mapping.json", help="Archivo JSON de mapeo")
        parser.add_argument("--dry-run", action="store_true", help="No escribe archivos, solo muestra conteos")

    def handle(self, *args, **opts):
        base = Path(settings.BASE_DIR)
        raw_dir = (base / opts["raw_dir"]).resolve()
        out_dir = (base / opts["out_dir"]).resolve()
        map_file = (base / opts["map"]).resolve()

        with open(map_file, "r", encoding="utf-8") as fh:
            mapping_cfg = json.load(fh)

        companies, accounts, centers, scenarios = set(), {}, set(), set()
        facts, periods_set = [], set()
        skipped_no_amount = 0

        for src_name, cfg in mapping_cfg.get("sources", {}).items():
            fpath = raw_dir / src_name
            if not fpath.exists():
                self.stderr.write(self.style.WARNING(f"Saltando (no existe): {src_name}"))
                continue

            # 1) Cargar sin asumir encabezado
            try:
                df = pd.read_csv(fpath, encoding="utf-8-sig", header=None)
            except UnicodeDecodeError:
                df = pd.read_csv(fpath, encoding="latin-1", header=None)

            # 2) Detectar encabezado
            hdr_idx = choose_header_row(df)
            if hdr_idx is not None:
                header = [str(x).strip() for x in df.iloc[hdr_idx].tolist()]
                df = df.iloc[hdr_idx + 1:].reset_index(drop=True)
                df.columns = normalize_headers(header)
                self.stdout.write(self.style.WARNING(f"{src_name}: cabecera detectada en fila {hdr_idx+1}."))
            else:
                header = [str(x).strip() for x in df.iloc[0].tolist()]
                df = df.iloc[1:].reset_index(drop=True)
                df.columns = normalize_headers(header)
                self.stdout.write(self.style.WARNING(f"{src_name}: cabecera forzada desde primera fila."))

            # 2b) Caso header en DOS filas (meses en la fila siguiente)
            #     Si hay varias col_* al final y la siguiente fila parece tener meses → usamos esos tokens.
            month_cols_hint = {}
            if len(df) > 0 and any(c.startswith("col_") for c in df.columns):
                next_tokens = [str(x).strip() for x in df.iloc[0].tolist()]
                # pair columns with tokens
                for col, tok in zip(df.columns, next_tokens):
                    if col.startswith("col_"):
                        # year por defecto lo obtendremos de defaults (def_year) más abajo
                        month_cols_hint[col] = tok  # de momento guardamos el token
                # aún no resolvemos a YYYY-MM; eso se hace tras leer defaults

            # 3) Renombres declarados
            if cfg.get("rename"):
                df = df.rename(columns=cfg["rename"])

            # 4) Defaults & columnas base
            guessed = guess_columns(df)
            m = cfg.get("columns", {})
            d = cfg.get("defaults", {})
            def_company  = d.get("company",  "MiEmpresa")
            def_period   = d.get("period",   "2025-01")
            def_account  = d.get("account",  "ingresos")
            def_center   = d.get("center",   "")
            def_scenario = d.get("scenario", "Base")
            def_year     = d.get("year") or int(def_period.split("-")[0])
            acc_type     = cfg.get("account_type", "OTHER")
            scn_kind     = cfg.get("scenario_kind", "ACTUAL")
            fixed_scn    = cfg.get("scenario_value")

            company_col  = match_col(df, m.get("company",  "Empresa"))  or guessed.get("Empresa")
            period_col   = match_col(df, m.get("period",   "Periodo"))  or guessed.get("Periodo")
            account_col  = match_col(df, m.get("account",  "Cuenta"))   or guessed.get("Cuenta")
            center_col   = match_col(df, m.get("center",   "Centro"))   or guessed.get("Centro")
            amount_col   = match_col(df, m.get("amount",   "Monto"))    or guessed.get("Monto")
            scenario_col = match_col(df, m.get("scenario", "Escenario"))or guessed.get("Escenario")

            # 5) Detección de columnas mensuales (wide) y unpivot
            #    Primero resolvemos 'month_cols_hint' usando el año por defecto si aplica.
            resolved_hint = {}
            if month_cols_hint:
                for col, tok in month_cols_hint.items():
                    p = period_from_header(tok, def_year)
                    if p:
                        resolved_hint[col] = p
                if len(resolved_hint) < 6:
                    resolved_hint = {}

            #    Intento por encabezados simples:
            auto_months = detect_month_columns(df, def_year)
            month_cols = auto_months or resolved_hint

            if month_cols:
                # Si los tokens de meses venían en la 2ª fila del header, esa fila es cabecera de meses → dropearla
                if resolved_hint:
                    df = df.iloc[1:].reset_index(drop=True)

                id_vars = []
                for col in [company_col, account_col, center_col, scenario_col, period_col]:
                    if col and col in df.columns:
                        id_vars.append(col)
                value_vars = list(month_cols.keys())
                tmp = df.melt(id_vars=id_vars, value_vars=value_vars,
                              var_name="__monthcol", value_name="Monto")
                tmp["Periodo"] = tmp["__monthcol"].map(month_cols)
                tmp.drop(columns=["__monthcol"], inplace=True)
                long_df = tmp
                uniq_periods = sorted(set(month_cols.values()))
                self.stdout.write(self.style.HTTP_INFO(
                    f"{src_name}: columnas mensuales detectadas={len(value_vars)} → periodos únicos={len(uniq_periods)}"
                ))
            else:
                long_df = df.copy()
                if amount_col is None:
                    skipped_no_amount += len(long_df)
                    continue

            # 6) Normalización columnas destino
            long_df["Empresa"]   = long_df[company_col]  if company_col  in long_df.columns else def_company
            long_df["Cuenta"]    = long_df[account_col]  if account_col  in long_df.columns else def_account
            long_df["Centro"]    = long_df[center_col]   if center_col   in long_df.columns else def_center
            scen_tmp             = long_df[scenario_col] if scenario_col in long_df.columns else ""
            long_df["Escenario"] = scen_tmp.fillna("").replace("", fixed_scn or def_scenario)

            if "Monto" not in long_df.columns and amount_col:
                long_df["Monto"] = long_df[amount_col]

            if "Periodo" not in long_df.columns or long_df["Periodo"].isna().all():
                if period_col:
                    long_df["Periodo"] = long_df.apply(
                        lambda r: build_period_code(r, period_col, def_period), axis=1
                    )
                else:
                    long_df["Periodo"] = def_period

            long_df["Monto"] = pd.to_numeric(
                long_df["Monto"].astype(str).str.replace(",", ""), errors="coerce"
            ).fillna(0.0)

            # 7) Volcado a colecciones de salida
            for _, row in long_df.iterrows():
                amount = float(row.get("Monto", 0) or 0)
                period_code = str(row.get("Periodo") or def_period).strip()
                company_name = str(row.get("Empresa") or def_company).strip()
                account_name = str(row.get("Cuenta") or def_account).strip()
                center_name  = str(row.get("Centro") or "").strip()
                scenario_name= str(row.get("Escenario") or def_scenario).strip()

                company_code  = slugify(company_name)
                account_code  = slugify(account_name)
                center_code   = slugify(center_name) if center_name else ""
                scenario_code = slugify(scenario_name)

                companies.add((company_code, company_name, "USD", True))
                accounts[account_code] = (account_code, account_name, cfg.get("account_type","OTHER"), "", 0, True)
                if center_code:
                    centers.add((center_code, center_name, "", 0, True))
                scenarios.add((scenario_code, scenario_name, cfg.get("scenario_kind","ACTUAL")))

                if re.match(r"^\d{4}-\d{2}$", period_code):
                    y, m = period_code.split("-")
                    periods_set.add((period_code, int(y), int(m), "", "", True))
                else:
                    periods_set.add((period_code, None, None, "", "", True))

                facts.append((company_code, period_code, account_code, center_code, scenario_code, amount))

            self.stdout.write(f"✔ {src_name}: filas={len(df)} → facts acumulados={len(facts)}")

        # 8) DataFrames salida
        df_companies = pd.DataFrame(list(companies), columns=["company_code","company_name","currency","is_active"]).sort_values("company_code")
        df_accounts  = pd.DataFrame(list(accounts.values()), columns=["account_code","account_name","account_type","parent_code","level","is_leaf"]).sort_values("account_code")
        df_centers   = pd.DataFrame(list(centers), columns=["center_code","center_name","parent_code","level","is_active"]).sort_values("center_code")
        df_periods   = pd.DataFrame(list(periods_set), columns=["period_code","year","month","start_date","end_date","is_open"]).sort_values("period_code")
        df_scenarios = pd.DataFrame(list(scenarios), columns=["scenario_code","scenario_name","kind"]).sort_values("scenario_code")
        df_facts     = pd.DataFrame(facts, columns=["company_code","period_code","account_code","center_code","scenario_code","amount"])

        self.stdout.write(self.style.HTTP_INFO(
            f"Generados: companies={len(df_companies)} accounts={len(df_accounts)} "
            f"centers={len(df_centers)} periods={len(df_periods)} "
            f"scenarios={len(df_scenarios)} facts={len(df_facts)}"
        ))
        if skipped_no_amount:
            self.stdout.write(self.style.WARNING(f"Filas saltadas por no detectar columna Monto: {skipped_no_amount}"))

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se escribieron archivos."))
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        df_companies.to_csv(out_dir / "companies.csv", index=False, encoding="utf-8-sig")
        df_accounts.to_csv(out_dir / "accounts.csv", index=False, encoding="utf-8-sig")
        df_centers.to_csv(out_dir / "cost_centers.csv", index=False, encoding="utf-8-sig")
        df_periods.to_csv(out_dir / "periods.csv", index=False, encoding="utf-8-sig")
        df_scenarios.to_csv(out_dir / "scenarios.csv", index=False, encoding="utf-8-sig")
        df_facts.to_csv(out_dir / "facts_finance.csv", index=False, encoding="utf-8-sig")

        self.stdout.write(self.style.SUCCESS(f"Escrito en {out_dir}"))
