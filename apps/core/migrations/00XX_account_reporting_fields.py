from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_company_code"),  # <-- ajusta al último nombre de tu migración existente
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="statement",
            field=models.CharField(
                max_length=8,
                null=True,
                blank=True,
                help_text="IS (Income Statement) o BS (Balance Sheet)",
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="group",
            field=models.CharField(
                max_length=64, null=True, blank=True, help_text="Grupo (Ventas, COGS, OPEX, Activos, etc.)"
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="subgroup",
            field=models.CharField(
                max_length=64, null=True, blank=True, help_text="Subgrupo/partida (Corriente, No corriente, etc.)"
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="order_index",
            field=models.IntegerField(
                null=True, blank=True, help_text="Orden de impresión/reporte (menor primero)"
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="natural_sign",
            field=models.SmallIntegerField(
                null=True,
                blank=True,
                choices=((1, "+1"), (-1, "-1")),
                help_text="Signo natural de la cuenta para normalizar importes (+1 activos/ventas, -1 costos/gastos/pasivos)",
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="measure",
            field=models.CharField(
                max_length=16,
                null=True,
                blank=True,
                help_text="flow (flujo del período, P&L) o balance (saldo, Balance General)",
            ),
        ),
    ]
