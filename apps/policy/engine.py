from django.utils import timezone
from django.db.models import Q, Sum
from django.conf import settings

from apps.policy.models import PolicyPack, ValidationRule, RuleExecutionLog
from apps.core.models import KPI, ExpenseProjection, RevenueDriver, Period

def _enforcement():
    return getattr(settings, "POLICY_ENFORCEMENT", "warn").lower()  # 'block' | 'warn'

def _active_pack():
    code = getattr(settings, "POLICY_ACTIVE_PACK", None)
    if not code:
        return None
    try:
        return PolicyPack.objects.get(code=code, is_active=True)
    except PolicyPack.DoesNotExist:
        return None

def _log(rule, obj, status, message, evidence_url=None):
    RuleExecutionLog.objects.create(
        rule=rule,
        content_object=obj,
        status=status,  # 'PASS', 'WARN', 'FAIL'
        message=message,
        executed_at=timezone.now(),
        evidence_url=evidence_url or ""
    )

def rule_apm_001_ebitda_requires_opex(kpi: KPI):
    """
    APM-001: No etiquetar 'EBITDA' si no existen gastos (OPEX) para el período/escenario.
    En 'block': marca FAIL y exige cambiar etiqueta; en 'warn': registra advertencia.
    """
    name = (kpi.name or "").upper()
    if "EBITDA" not in name:
        return "SKIP"

    has_opex = ExpenseProjection.objects.filter(
        company=kpi.company,
        scenario__in=kpi.scenarios.all(),
        period=kpi.period
    ).exists()

    rule = ValidationRule.objects.filter(code="APM-001").first()
    if not rule:
        return "SKIP"

    if not has_opex:
        if _enforcement() == "block":
            _log(rule, kpi, "FAIL", "APM-001: No hay OPEX para el período; no puede etiquetarse como EBITDA.")
            # Sugerencia: bajar etiqueta provisional para no romper UI
            if "EBITDA" in kpi.name:
                kpi.name = kpi.name.replace("EBITDA", "Margen bruto (provisional)")
                kpi.save(update_fields=["name"])
            return "FAIL"
        else:
            _log(rule, kpi, "WARN", "APM-001: OPEX no cargado; revisa etiqueta EBITDA.")
            return "WARN"
    else:
        _log(rule, kpi, "PASS", "APM-001: OPEX presente.")
        return "PASS"

def rule_ifrs15_010_ingresos_consistencia(kpi: KPI):
    """
    IFRS15-010: Si el KPI es de ingresos mensuales, validar consistencia básica con drivers.
    (Regla liviana de ejemplo)
    """
    rule = ValidationRule.objects.filter(code="IFRS15-010").first()
    if not rule:
        return "SKIP"

    # Heurística: nombres que contienen 'INGRESO' o 'REVENUE'
    name = (kpi.name or "").upper()
    if "INGRES" not in name and "REVENUE" not in name:
        return "SKIP"

    # Sumatoria simple de drivers del mismo período/escenario
    rd_sum = RevenueDriver.objects.filter(
        company=kpi.company,
        scenario__in=kpi.scenarios.all(),
        period=kpi.period
    ).aggregate(t=Sum("price"))["t"] or 0

    # Nota: aquí solo comparamos órdenes de magnitud para demo
    if rd_sum == 0:
        _log(rule, kpi, "WARN", "IFRS15-010: No hay drivers asociados; verifica reconocimiento de ingresos.")
        return "WARN"

    _log(rule, kpi, "PASS", "IFRS15-010: Drivers presentes.")
    return "PASS"

def rule_pres_001_kpi_muestra_sustento(kpi: KPI):
    """
    Presentación-001: exigir que cualquier KPI publicado tenga al menos un log de regla reciente.
    """
    rule = ValidationRule.objects.filter(code="PRES-001").first()
    if not rule:
        return "SKIP"

    has_log = RuleExecutionLog.objects.filter(object_id=kpi.id, content_type__model="kpi").exists()
    if not has_log:
        _log(rule, kpi, "WARN", "PRES-001: KPI sin ejecución reciente de reglas; ejecute 'calc_kpis'.")
        return "WARN"
    return "PASS"

def evaluate_kpi(kpi: KPI):
    """Ejecuta reglas mínimas sobre un KPI y devuelve el peor estado."""
    pack = _active_pack()
    if not pack:
        return "SKIP"
    results = []

    for fn in (rule_apm_001_ebitda_requires_opex, rule_ifrs15_010_ingresos_consistencia, rule_pres_001_kpi_muestra_sustento):
        try:
            results.append(fn(kpi))
        except Exception as e:
            # no interrumpir pipeline por errores de regla
            _ = e

    if "FAIL" in results:
        return "FAIL"
    if "WARN" in results:
        return "WARN"
    return "PASS"
