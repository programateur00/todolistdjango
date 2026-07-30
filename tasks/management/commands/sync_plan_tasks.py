"""
Crea la tarea de los planes que no la tengan.

Hace falta para los planes creados antes de que existiera esa
generación automática, y para los creados desde el admin antes del
arreglo. Sin su tarea, un plan existe pero nunca aparece en la lista —
y desde fuera parece que el plan no funciona.

Es idempotente: pasarlo dos veces no duplica nada.
"""
from django.core.management.base import BaseCommand

from tasks.models import Plan


class Command(BaseCommand):
    help = "Genera la tarea de los planes que no la tengan."

    def handle(self, *args, **options):
        arreglados, ya_estaban, sin_ejercicios = 0, 0, 0

        for plan in Plan.objects.filter(deleted_at__isnull=True):
            if not plan.items.filter(exercise__isnull=False).exists():
                sin_ejercicios += 1
                self.stdout.write(
                    f"  · {plan.name}: sin ejercicios, no se genera tarea"
                )
                continue

            if plan.task:
                ya_estaban += 1
                continue

            task = plan.sync_task()
            if task:
                arreglados += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {plan.name}: tarea creada para el {task.due_date}"
                ))

        self.stdout.write("")
        self.stdout.write(
            f"Listo. {arreglados} arreglado(s), {ya_estaban} ya la tenían, "
            f"{sin_ejercicios} sin ejercicios."
        )
        if sin_ejercicios:
            self.stdout.write(
                "Los planes sin ejercicios no generan tarea: añádeles al menos "
                "un objetivo con ejercicio y vuelve a ejecutar esto."
            )
