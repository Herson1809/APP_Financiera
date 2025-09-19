from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=64, blank=True, default="")
    currency = models.CharField(max_length=8, default="USD")
    code = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.name


class Scenario(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        unique_together = ("company", "name")

    def __str__(self):
        return self.name


class Period(models.Model):
    year = models.IntegerField()
    month = models.IntegerField()

    class Meta:
        unique_together = ("year", "month")

    def __str__(self):
        return f"{self.year}-{str(self.month).zfill(2)}"


class Assumption(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    key = models.CharField(max_length=64)
    value = models.FloatField()
    unit = models.CharField(max_length=16, default="ratio")
    notes = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("company", "scenario", "period", "key")


class RevenueDriver(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    product = models.CharField(max_length=120, blank=True, default="General")
    price = models.FloatField()
    units = models.FloatField()
    currency = models.CharField(max_length=8, default="USD")
    notes = models.TextField(blank=True, default="")


class ExpenseProjection(models.Model):
    DRIVER_TYPES = (("percent_of_sales", "Percent of Sales"), ("fixed", "Fixed"))
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    line_item_code = models.CharField(max_length=64)
    line_item_name = models.CharField(max_length=128)
    driver_type = models.CharField(max_length=32, choices=DRIVER_TYPES)
    value = models.FloatField()
    currency = models.CharField(max_length=8, default="USD")
    notes = models.TextField(blank=True, default="")


class DebtInstrument(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    principal = models.FloatField()
    rate_annual = models.FloatField()
    term_months = models.IntegerField()
    start_date = models.DateField()
    payment_frequency = models.CharField(max_length=16, default="monthly")
    currency = models.CharField(max_length=8, default="USD")
    notes = models.TextField(blank=True, default="")


class AmortizationSchedule(models.Model):
    debt = models.ForeignKey(DebtInstrument, on_delete=models.CASCADE, related_name="schedule")
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    installment = models.FloatField()
    interest = models.FloatField()
    principal = models.FloatField()
    balance = models.FloatField()


class IncomeStatement(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    revenue = models.FloatField(default=0)
    cogs = models.FloatField(default=0)
    gross_profit = models.FloatField(default=0)
    opex = models.FloatField(default=0)
    ebitda = models.FloatField(default=0)
    depreciation = models.FloatField(default=0)
    ebit = models.FloatField(default=0)
    interest = models.FloatField(default=0)
    ebt = models.FloatField(default=0)
    tax = models.FloatField(default=0)
    net_income = models.FloatField(default=0)


class BalanceSheet(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    total_assets = models.FloatField(default=0)
    total_liabilities = models.FloatField(default=0)
    total_equity = models.FloatField(default=0)


class CashFlowStatement(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    cfo = models.FloatField(default=0)
    cfi = models.FloatField(default=0)
    cff = models.FloatField(default=0)
    net_change_cash = models.FloatField(default=0)


class KPI(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    value = models.FloatField()
    unit = models.CharField(max_length=16, default="ratio")

    class Meta:
        unique_together = ("company", "scenario", "period", "name")


class Framework(models.Model):
    code = models.SlugField(unique=True, help_text="Ej: nif, nias, coso-erm, iso-31000")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class FrameworkSection(models.Model):
    framework = models.ForeignKey(Framework, on_delete=models.CASCADE, related_name="sections")
    code = models.CharField(max_length=80, help_text="Ej: IAS 1, IFRS 15, ISA 315, Principio 4")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ("framework", "code")

    def __str__(self):
        return f"{self.framework.code.upper()} - {self.code}: {self.title}"


class KPIFrameworkLink(models.Model):
    kpi = models.ForeignKey("KPI", on_delete=models.CASCADE, related_name="framework_links")
    section = models.ForeignKey(FrameworkSection, on_delete=models.CASCADE, related_name="kpi_links")
    rationale = models.TextField(blank=True, help_text="Por qué este KPI se sustenta en esta sección")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("kpi", "section")

    def __str__(self):
        return f"{self.kpi.name} ↔ {self.section}"


# ==== Catálogo contable y hechos financieros ====
class Account(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=64, null=True, blank=True)

    # ---- Campos de reporting ----
    statement = models.CharField(max_length=8, null=True, blank=True)
    group = models.CharField(max_length=64, null=True, blank=True)
    subgroup = models.CharField(max_length=64, null=True, blank=True)
    order_index = models.IntegerField(null=True, blank=True)
    natural_sign = models.SmallIntegerField(
        null=True, blank=True, choices=((1, "+1"), (-1, "-1"))
    )
    measure = models.CharField(max_length=16, null=True, blank=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class CostCenter(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.code} - {self.name or 'Centro'}"


class FactFinance(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    center = models.ForeignKey(CostCenter, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=["company", "scenario", "period"]),
            models.Index(fields=["account"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "account", "scenario", "period", "center"],
                name="uniq_factfinance_key",
            ),
        ]

    def __str__(self):
        return f"{self.company} {self.scenario} {self.period} {self.account} = {self.amount}"
