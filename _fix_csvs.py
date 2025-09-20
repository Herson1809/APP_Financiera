# _fix_csvs.py
# Normaliza facts_export.csv a los CSV que pide import_fin_data:
#   companies.csv, accounts.csv, cost_centers.csv, periods.csv,
#   scenarios.csv, facts_finance.csv
#
# Ubicación recomendada: junto a manage.py
# Uso: python _fix_csvs.py   (lee facts_export.csv en la misma carpeta)

import csv, re, os, sys, calendar
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent
SRC = BASE_DIR / "facts_export.csv"           # origen
OUTDIR = BASE_DIR / "import_data" / "templates"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ---------- utilidades ----------
def codeify(s: str, maxlen: int = 20):
    s = (s or "").strip()
    if not s:
        return "CODE"
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    if not s:
        s = "CODE"
    return s[:maxlen]

def last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]

# Mapeo de tipos de cuenta + heurística
MAP = {
    "Ventas": "REVENUE",
    "Compras de materia prima": "COGS",
    "Gastos de personal obrero": "COGS",
    "Gastos de personal administrativo": "OPEX",
    "Gastos de Servicios generales": "OPEX",
    "Gasto de depreciación Mobiliario y enseres": "DEPR",
    "Gasto de depreciación Maquinarias planta": "DEPR",
    "Costos financieros": "FIN",
    "Impuestos sobre beneficios": "TAX",
}
def guess_type(name: str):
    n = (name or "").lower()
    if "venta" in n: return "REVENUE"
    if "compra" in n or "materia prima" in n or "costo" in n: return "COGS"
    if "depreci" in n or "amortiz" in n: return "DEPR"
    if "financ" in n: return "FIN"
    if "impuest" in n: return "TAX"
    return "OPEX"

# ---------- lee el origen ----------
if not SRC.exists():
    print(f"[ERROR] No encuentro {SRC}. Déjalo junto a _fix_csvs.py.")
    sys.exit(1)

rows = []
with open(SRC, "r", encoding="utf-8-sig", newline="") as f:
    r = csv.DictReader(f)
    req = {"Empresa","Escenario","Año","Mes","Cuenta","Monto"}
    if not req.issubset(set(r.fieldnames or [])):
        print("[ERROR] El CSV de origen debe tener columnas:", ", ".join(sorted(req)))
        print("Columnas encontradas:", r.fieldnames)
        sys.exit(1)
    for row in r:
        try:
            row["_year"]   = int(str(row["Año"]).strip())
            row["_month"]  = int(str(row["Mes"]).strip())
            # Normaliza monto con coma o punto
            raw_m = str(row["Monto"]).replace(",", ".")
            row["_amount"] = float(raw_m)
            rows.append(row)
        except Exception as e:
            print("Fila inválida, la salto:", row, "->", e)

if not rows:
    print("[WARN] No hay filas válidas en facts_export.csv")
    sys.exit(0)

# ---------- catálogos ----------
# companies
name2ccode, companies = {}, []
for r in rows:
    nm = r["Empresa"].strip()
    if nm not in name2ccode:
        ccode = codeify(nm)
        # maneja posibles colisiones de código
        base, i = ccode, 2
        while any(c["company_code"] == ccode for c in companies):
            ccode = f"{base}_{i}"[:20]; i += 1
        name2ccode[nm] = ccode
        companies.append({
            "company_code": ccode,
            "company_name": nm,
            "currency": "USD",
            "is_active": "TRUE",
        })

# scenarios
scn2code, scenarios = {}, []
for r in rows:
    scn = (r.get("Escenario") or "BASE").strip() or "BASE"
    if scn not in scn2code:
        scode = codeify(scn)
        scn2code[scn] = scode
        scenarios.append({
            "scenario_code": scode,
            "scenario_name": scn,
            "kind": "ACTUAL",  # puedes cambiarlo si luego usas 'BUDGET'/'FORECAST'
        })

# accounts
acc2code, account_rows = {}, []
for r in rows:
    an = r["Cuenta"].strip()
    if an not in acc2code:
        acode = codeify(an)
        base, i = acode, 2
        while any(a["account_code"] == acode for a in account_rows):
            acode = f"{base}_{i}"[:20]; i += 1
        acc2code[an] = acode
        atype = MAP.get(an) or guess_type(an)
        account_rows.append({
            "account_code": acode,
            "account_name": an,
            "account_type": atype,
            "parent_code": "",
            "level": 1,
            "is_leaf": "TRUE",
        })

# periods
periods = {}
for r in rows:
    y, m = r["_year"], r["_month"]
    pcode = f"{y}{m:02d}"
    if pcode not in periods:
        start = date(y, m, 1)
        end = date(y, m, last_day(y, m))
        periods[pcode] = {
            "period_code": pcode,
            "year": y,
            "month": m,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "is_open": "TRUE",
        }

# cost centers (mínimo 1 por ahora)
centers = [{
    "center_code": "MAIN",
    "center_name": "Centro Principal",
    "parent_code": "",
    "level": 1,
    "is_active": "TRUE",
}]

# ---------- facts_finance ----------
facts = []
for r in rows:
    company_code  = name2ccode[r["Empresa"].strip()]
    period_code   = f'{r["_year"]}{r["_month"]:02d}'
    account_code  = acc2code[r["Cuenta"].strip()]
    center_code   = "MAIN"
    scenario_code = scn2code[(r.get("Escenario") or "BASE").strip() or "BASE"]
    amount        = f'{r["_amount"]:.2f}'
    facts.append({
        "company_code":  company_code,
        "period_code":   period_code,
        "account_code":  account_code,
        "center_code":   center_code,
        "scenario_code": scenario_code,
        "amount":        amount,
    })

# ---------- escribe CSVs ----------
def write_csv(path: Path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

write_csv(OUTDIR / "companies.csv",
          ["company_code","company_name","currency","is_active"],
          companies)

write_csv(OUTDIR / "accounts.csv",
          ["account_code","account_name","account_type","parent_code","level","is_leaf"],
          account_rows)

write_csv(OUTDIR / "cost_centers.csv",
          ["center_code","center_name","parent_code","level","is_active"],
          centers)

write_csv(OUTDIR / "periods.csv",
          ["period_code","year","month","start_date","end_date","is_open"],
          sorted(periods.values(), key=lambda x: x["period_code"]))

write_csv(OUTDIR / "scenarios.csv",
          ["scenario_code","scenario_name","kind"],
          scenarios)

write_csv(OUTDIR / "facts_finance.csv",
          ["company_code","period_code","account_code","center_code","scenario_code","amount"],
          facts)

print("Listo ✅")
print(f"Generado en: {OUTDIR}")
print(f"companies={len(companies)}  accounts={len(account_rows)}  periods={len(periods)}  scenarios={len(scenarios)}  facts={len(facts)}")
