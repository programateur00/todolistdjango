"""
Comando de gestión: marca como "no hecho" las tareas cuya hora límite
ya ha pasado sin haber sido completadas.

Uso en cron (cada minuto):
    * * * * * /ruta/al/venv/bin/python /ruta/proyecto/manage.py expire_tasks

O manualmente:
    python3 manage.py expire_tasks
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from tasks.models import Task


class Command(BaseCommand):
    help = "Auto-marca como no hecha cualquier tarea cuya hora límite ya pasó."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Muestra qué tareas expiraría sin modificar la BD.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now_local = timezone.localtime(timezone.now()).replace(tzinfo=None)
        today = now_local.date()
        now_time = now_local.time()

        # Tareas pendientes con due_time definido
        candidates = Task.objects.filter(
            is_done=False,
            expired=False,
            due_time__isnull=False,
        )

        expired_count = 0
        for task in candidates:
            if task.due_date is None:
                should_expire = task.due_time < now_time
            else:
                deadline = datetime.datetime.combine(task.due_date, task.due_time)
                should_expire = now_local > deadline

            if should_expire:
                if not dry_run:
                    task.mark_expired()
                self.stdout.write(
                    self.style.WARNING(
                        f"{'[DRY] ' if dry_run else ''}Expirada: «{task.title}» "
                        f"(límite: {task.due_time:%H:%M})"
                    )
                )
                expired_count += 1

        if expired_count:
            self.stdout.write(
                self.style.SUCCESS(f"{expired_count} tarea(s) {'encontradas' if dry_run else 'marcadas'} como expiradas.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Sin tareas expiradas en este ciclo."))
