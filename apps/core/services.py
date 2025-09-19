# apps/core/services.py
from decimal import Decimal

# ========================
# Report building functions (placeholders existentes)
# ========================

def build_income_statement(scenario_id: int):
    # TODO: implementar si necesitas un EERR estructurado más adelante
    return {}

def build_balance_sheet(scenario_id: int):
    return {"total_assets": 0.0, "total_liabilities": 0.0, "total_equity": 0.0}

def build_cash_flow(scenario_id: int):
    return {"cash_begin": 0.0, "cash_net": 0.0, "cash_end": 0.0}


# ========================
# Helpers de análisis existentes
# ========================

def calculate_vertical(account_totals: dict, total_sales: Decimal) -> dict:
    """Análisis vertical: cada cuenta como % de ventas."""
    result = {}
    total_sales = Decimal(total_sales or 0)
    for account, amount in account_totals.items():
        amt = Decimal(amount or 0)
        result[account] = round((amt / total_sales) * 100, 2) if total_sales != 0 else 0
    return result


def calculate_horizontal(current_data: dict, previous_data: dict) -> dict:
    """Análisis horizontal: variación absoluta y % vs año anterior."""
    result = {}
    for account, current_amount in current_data.items():
        curr = Decimal(current_amount or 0)
        prev = Decimal(previous_data.get(account, 0) or 0)
        abs_var = curr - prev
        perc_var = round((abs_var / prev) * 100, 2) if prev else None
        result[account] = {"abs": abs_var, "perc": perc_var}
    return result


# ========================
# NUEVO: Categorización heurística y márgenes
# ========================

def detect_sales_name(account_totals: dict) -> str | None:
    for key in ("Ventas", "Ingresos", "Sales", "Revenue"):
        if key in account_totals:
            return key
    for k in account_totals.keys():
        kl = (k or "").lower()
        if ("venta" in kl) or ("ingres" in kl) or ("sales" in kl) or ("revenue" in kl):
            return k
    return None


def categorize_accounts(account_totals: dict[str, Decimal]) -> dict:
    """
    Heurística por nombre para agrupar cuentas.
    Devuelve dict con sumas por categoría y mapping por cuenta.
    Categorías: REVENUE, COGS, OPEX, DA, INTEREST, TAX, OTHER_OP, OTHER_NP
    """
    sums = {
        "REVENUE": Decimal("0"),
        "COGS": Decimal("0"),
        "OPEX": Decimal("0"),
        "DA": Decimal("0"),
        "INTEREST": Decimal("0"),
        "TAX": Decimal("0"),
        "OTHER_OP": Decimal("0"),
        "OTHER_NP": Decimal("0"),
    }
    mapping = {}

    sales_name = detect_sales_name(account_totals)

    for name, val in account_totals.items():
        amt = Decimal(val or 0)
        n = (name or "").lower()

        # Prioridades: revenue explícito
        if sales_name and name == sales_name:
            sums["REVENUE"] += amt
            mapping[name] = "REVENUE"
            continue
        if any(k in n for k in ("ingres", "ventas", "sales", "revenue")):
            sums["REVENUE"] += amt
            mapping[name] = "REVENUE"
            continue

        # COGS
        if any(k in n for k in ("costo", "cogs", "cost of goods")):
            sums["COGS"] += amt
            mapping[name] = "COGS"
            continue

        # Depreciación / Amortización
        if any(k in n for k in ("deprec", "amort")):
            sums["DA"] += amt
            mapping[name] = "DA"
            continue

        # Intereses
        if any(k in n for k in ("interes", "interest")):
            sums["INTEREST"] += amt
            mapping[name] = "INTEREST"
            continue

        # Impuestos
        if any(k in n for k in ("impuest", "tax")):
            sums["TAX"] += amt
            mapping[name] = "TAX"
            continue

        # OPEX (operativos)
        if any(k in n for k in ("gasto", "opex", "operac", "admin", "ventas ")):  # espacio evita confundir 'Ventas'
            sums["OPEX"] += amt
            mapping[name] = "OPEX"
            continue

        # Otros
        # Heurística simple: si es positivo y no clasifica, OTHER_OP; si es negativo, OTHER_NP.
        if amt >= 0:
            sums["OTHER_OP"] += amt
            mapping[name] = "OTHER_OP"
        else:
            sums["OTHER_NP"] += amt
            mapping[name] = "OTHER_NP"

    return {"sums": sums, "mapping": mapping}


def compute_income_margins(cats: dict) -> dict:
    """
    Calcula márgenes clave a partir de sumas por categoría.
    - Gross Profit = Revenue - COGS
    - EBITDA = Revenue - COGS - OPEX
    - EBIT = EBITDA - DA
    - Net Income = EBIT - INTEREST - TAX + OTHER_OP + OTHER_NP
    """
    s = cats["sums"]
    revenue = s["REVENUE"]
    cogs = s["COGS"]
    opex = s["OPEX"]
    da = s["DA"]
    interest = s["INTEREST"]
    tax = s["TAX"]
    other_op = s["OTHER_OP"]
    other_np = s["OTHER_NP"]

    gross = revenue - cogs
    ebitda = revenue - cogs - opex
    ebit = ebitda - da
    net = ebit - interest - tax + other_op + other_np

    return {
        "GROSS_PROFIT": gross,
        "EBITDA": ebitda,
        "EBIT": ebit,
        "NET_INCOME": net,
    }
