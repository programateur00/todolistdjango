"""
Cierra los planes de Estudio con curso de Udemy que se quedaron abiertos
con el curso ya al 100%.

El fallo: el 100% llegaba a la barra del objetivo por la vía pasiva de la
extensión (sin sesión contando) y el cierre no se disparaba. Ya está
corregido de raíz (Plan.finish_udemy_course), pero los planes que se
atascaron antes siguen abiertos hasta que se cierren aquí (o hasta la
próxima carga de la lista, que también los barre).

Idempotente. Con --dry-run solo lista lo que cerraría.

    python manage.py cerrar_planes_udemy_atascados --dry-run
    python manage.py cerrar_planes_udemy_atascados
"""
from django.core.management.base import BaseCommand

from tasks.models import Plan


class Command(BaseCommand):
    help = "Cierra los planes de Udemy abiertos cuyo curso ya está al 100%."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo listar, no cerrar.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        cerrados = 0
        qs = Plan.objects.filter(
            deleted_at__isnull=True, closed_at__isnull=True, is_active=True,
            plan_type=Plan.PLAN_TYPE_STUDY,
        )
        for plan in qs:
            head = plan.headline
            if not (head and head.is_udemy_course) or not plan._udemy_course_done(head):
                continue
            self.stdout.write(f"  · {plan.name} (id {plan.pk}): curso al 100% -> {'se cerraría' if dry else 'cerrado'}")
            if not dry:
                plan.finish_udemy_course()
            cerrados += 1
        self.stdout.write(self.style.SUCCESS(f"{cerrados} plan(es) {'por cerrar' if dry else 'cerrados'}."))
