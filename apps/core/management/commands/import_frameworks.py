import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core.models import Framework, FrameworkSection, KPI, KPIFrameworkLink

class Command(BaseCommand):
    help = "Importa marcos y secciones (y vincula KPIs) desde un JSON. Ej: import_frameworks library.json"

    def add_arguments(self, parser):
        parser.add_argument("json_path", help="Ruta al JSON de biblioteca")
        parser.add_argument("--prune", action="store_true",
                            help="Elimina secciones existentes que no esten en el archivo")
        parser.add_argument("--dry-run", action="store_true",
                            help="No guarda cambios (transaccion revertida)")

    def handle(self, json_path, prune=False, dry_run=False, **kwargs):
        p = Path(json_path)
        if not p.exists():
            self.stderr.write(self.style.ERROR(f"No existe: {p}"))
            return

        # Soporta UTF-8 con y sin BOM
        data = json.loads(p.read_text(encoding="utf-8-sig"))

        fw_count = 0
        sec_count = 0
        link_count = 0

        @transaction.atomic
        def _do_import():
            nonlocal fw_count, sec_count, link_count

            for fw in data.get("frameworks", []):
                f, _ = Framework.objects.update_or_create(
                    code=fw["code"],
                    defaults={
                        "name": fw.get("name", fw["code"]),
                        "description": fw.get("description", ""),
                        "url": fw.get("url", "")
                    }
                )
                fw_count += 1

                existing = set(f.sections.values_list("code", flat=True))
                seen = set()

                for s in fw.get("sections", []):
                    sec, _ = FrameworkSection.objects.update_or_create(
                        framework=f,
                        code=s["code"],
                        defaults={
                            "title": s.get("title", s["code"]),
                            "text": s.get("text", "")
                        }
                    )
                    sec_count += 1
                    seen.add(s["code"])

                if prune:
                    to_delete = existing - seen
                    if to_delete:
                        FrameworkSection.objects.filter(framework=f, code__in=to_delete).delete()

            # Vinculaciones KPI–Marco (opcional)
            for link in data.get("links", []):
                ref = link.get("section")
                if not ref or ":" not in ref:
                    continue
                fw_code, sec_code = ref.split(":", 1)
                try:
                    sec = FrameworkSection.objects.get(framework__code=fw_code, code=sec_code)
                except FrameworkSection.DoesNotExist:
                    self.stderr.write(self.style.WARNING(f"Seccion no encontrada para vincular: {ref}"))
                    continue

                names = link.get("kpi_names", [])
                for namefrag in names:
                    for k in KPI.objects.filter(name__icontains=namefrag):
                        KPIFrameworkLink.objects.get_or_create(kpi=k, section=sec)
                        link_count += 1

            if dry_run:
                raise RuntimeError("Dry-run: transaccion revertida")

        try:
            _do_import()
            self.stdout.write(self.style.SUCCESS(
                f"Importados {fw_count} marcos, {sec_count} secciones, {link_count} vinculos"
            ))
        except RuntimeError as ex:
            self.stdout.write(self.style.WARNING(str(ex)))
