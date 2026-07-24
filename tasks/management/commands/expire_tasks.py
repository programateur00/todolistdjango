"""
Comando de gestión: marca como "no hecho" las tareas cuya hora límite
ya ha pasado sin haber sido completadas.

Nota: la app también hace esta comprobación sola cada vez que abres
la lista de tareas (ver Task.expire_overdue en models.py), así que
este comando ya NO es obligatorio para que funcione. Se deja aquí por
si en algún momento tienes un cron disponible (hosting de pago, tu
propio servidor, etc.) y prefieres que se revise en segundo plano
aunque no abras la app.

Uso en cron (cada minuto):
    * * * * * /ruta/al/venv/bin/python /ruta/proyecto/manage.py expire_tasks

O manualmente:
    python3 manage.py expire_tasks
"""

from django.core.management.base import BaseCommand

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
        expired = Task.expire_overdue(dry_run=dry_run)

        for task in expired:
            self.stdout.write(
                self.style.WARNING(
                    f"{'[DRY] ' if dry_run else ''}Expirada: «{task.title}» "
                    f"(límite: {task.due_time:%H:%M})"
                )
            )

        if expired:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(expired)} tarea(s) {'encontradas' if dry_run else 'marcadas'} como expiradas."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Sin tareas expiradas en este ciclo."))
