from django.core.management.base import BaseCommand
from apps.core.models import Framework, FrameworkSection

DATA = {
    "nif": {
        "name": "NIIF / NIF",
        "sections": [
            ("IAS 1",  "Presentación de estados financieros"),
            ("IAS 7",  "Estado de flujos de efectivo"),
            ("IFRS 15","Ingresos de contratos con clientes"),
        ],
    },
    "nias": {
        "name": "NIAS / ISA",
        "sections": [
            ("ISA 315", "Identificación y valoración de riesgos"),
            ("ISA 330", "Respuestas a los riesgos valorados"),
        ],
    },
    "coso-erm": {
        "name": "COSO ERM",
        "sections": [
            ("Componente 3", "Desempeño (selección y evaluación de riesgos)"),
            ("Componente 5", "Revisión y mejora"),
        ],
    },
    "iso-31000": {
        "name": "ISO 31000",
        "sections": [
            ("Cláusula 6", "Proceso de gestión del riesgo"),
            ("Cláusula 8", "Registro y reporte"),
        ],
    },
}

class Command(BaseCommand):
    help = "Crea marcos de referencia y secciones básicas"

    def handle(self, *args, **opts):
        created_fw = created_sec = 0
        for code, cfg in DATA.items():
            fw, fw_created = Framework.objects.get_or_create(code=code, defaults={"name": cfg["name"]})
            created_fw += int(fw_created)
            for code_sec, title in cfg["sections"]:
                _, sec_created = FrameworkSection.objects.get_or_create(
                    framework=fw, code=code_sec, defaults={"title": title}
                )
                created_sec += int(sec_created)
        self.stdout.write(self.style.SUCCESS(f"Marcos nuevos: {created_fw} | Secciones nuevas: {created_sec}"))
