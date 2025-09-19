from django.contrib import admin
from .models import (
    Company, Scenario, Period,
    Account, CostCenter, FactFinance,
    KPI, IncomeStatement, BalanceSheet, CashFlowStatement,
    Framework, FrameworkSection, KPIFrameworkLink,
    Assumption, RevenueDriver, ExpenseProjection,
    DebtInstrument, AmortizationSchedule
)

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "statement", "group", "subgroup", "order_index", "natural_sign", "measure")
    search_fields = ("code", "name")
    list_filter = ("statement", "group", "subgroup", "measure", "natural_sign")
    ordering = ("code",)

@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    ordering = ("code",)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country", "currency")
    search_fields = ("name", "code")

@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("company", "name", "created_at", "is_locked")
    list_filter = ("company", "is_locked")
    search_fields = ("name",)

@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ("year", "month")
    list_filter = ("year", "month")
    ordering = ("year", "month")

@admin.register(FactFinance)
class FactFinanceAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "account", "center", "amount")
    list_filter = ("company", "scenario", "period__year", "period__month", "account")
    search_fields = ("account__code", "account__name")

@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "name", "value", "unit")
    list_filter = ("company", "scenario", "period__year", "period__month")
    search_fields = ("name",)

@admin.register(IncomeStatement)
class IncomeStatementAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "revenue", "cogs", "gross_profit", "ebitda", "net_income")
    list_filter = ("company", "scenario", "period__year", "period__month")

@admin.register(BalanceSheet)
class BalanceSheetAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "total_assets", "total_liabilities", "total_equity")
    list_filter = ("company", "scenario", "period__year", "period__month")

@admin.register(CashFlowStatement)
class CashFlowStatementAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "cfo", "cfi", "cff", "net_change_cash")
    list_filter = ("company", "scenario", "period__year", "period__month")

@admin.register(Framework)
class FrameworkAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

@admin.register(FrameworkSection)
class FrameworkSectionAdmin(admin.ModelAdmin):
    list_display = ("framework", "code", "title")
    list_filter = ("framework",)
    search_fields = ("code", "title")

@admin.register(KPIFrameworkLink)
class KPIFrameworkLinkAdmin(admin.ModelAdmin):
    list_display = ("kpi", "section", "created_at")
    list_filter = ("section__framework",)

@admin.register(Assumption)
class AssumptionAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "key", "value", "unit")
    list_filter = ("company", "scenario", "period__year", "period__month")

@admin.register(RevenueDriver)
class RevenueDriverAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "product", "price", "units", "currency")

@admin.register(ExpenseProjection)
class ExpenseProjectionAdmin(admin.ModelAdmin):
    list_display = ("company", "scenario", "period", "line_item_code", "line_item_name", "driver_type", "value")

@admin.register(DebtInstrument)
class DebtInstrumentAdmin(admin.ModelAdmin):
    list_display = ("company", "name", "principal", "rate_annual", "term_months", "start_date", "currency")

@admin.register(AmortizationSchedule)
class AmortizationScheduleAdmin(admin.ModelAdmin):
    list_display = ("debt", "period", "installment", "interest", "principal", "balance")
