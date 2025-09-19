
from django.db import models

class Standard(models.Model):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)

class StandardSection(models.Model):
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE)
    section_code = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    summary = models.TextField()
    reference_url = models.URLField(blank=True, default="")
    version = models.CharField(max_length=24, default="1.0.0")
    effective_date = models.DateField(null=True, blank=True)
    jurisdiction = models.CharField(max_length=64, blank=True, default="")

class Control(models.Model):
    name = models.CharField(max_length=128)
    objective = models.TextField(blank=True, default="")
    sections = models.ManyToManyField(StandardSection, blank=True, related_name="controls")

class ValidationRule(models.Model):
    control = models.ForeignKey(Control, on_delete=models.CASCADE, related_name="rules")
    code = models.CharField(max_length=32)
    severity = models.CharField(max_length=8, choices=(("info","info"),("warn","warn"),("block","block")))
    logic_json = models.JSONField(default=dict)
    failure_message = models.CharField(max_length=240)
    version = models.CharField(max_length=24, default="1.0.0")

class PolicyPack(models.Model):
    name = models.CharField(max_length=64)
    country = models.CharField(max_length=64, blank=True, default="")
    industry = models.CharField(max_length=64, blank=True, default="")
    rules = models.ManyToManyField(ValidationRule, blank=True)

class RuleExecutionLog(models.Model):
    rule = models.ForeignKey(ValidationRule, on_delete=models.SET_NULL, null=True)
    context = models.CharField(max_length=64)
    context_id = models.CharField(max_length=64)
    executed_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=16)
    details = models.JSONField(default=dict)

class NonConformity(models.Model):
    rule = models.ForeignKey(ValidationRule, on_delete=models.SET_NULL, null=True)
    message = models.TextField()
    status = models.CharField(max_length=16, choices=(("open","open"),("closed","closed")), default="open")
    owner = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

class Evidence(models.Model):
    control = models.ForeignKey(Control, on_delete=models.CASCADE, related_name="evidences")
    kind = models.CharField(max_length=32, default="document")
    url = models.URLField(blank=True, default="")
    file_hash = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
