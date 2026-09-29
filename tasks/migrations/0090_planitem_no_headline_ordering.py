# Quita el "ejercicio estrella" de los planes de Deporte (pedido de Alex,
# 2026-09-30): el orden de los ejercicios pasa a ser SOLO `order`, así
# cualquiera se puede subir o bajar (antes el destacado iba siempre primero
# por Meta.ordering = ["-is_headline", "order", "pk"] y no tenía flechas).
#
# Para que nada cambie de sitio al desplegar, se renumera `order` (0,1,2...)
# siguiendo EXACTAMENTE el orden que se veía hasta ahora (destacado primero)
# y después se limpia is_headline en los planes de Deporte. Estudio/General
# no se tocan: su único objetivo sigue marcado.

from django.db import migrations


def renumber_and_clear(apps, schema_editor):
    Plan = apps.get_model("tasks", "Plan")
    PlanItem = apps.get_model("tasks", "PlanItem")
    for plan in Plan.objects.all():
        items = list(PlanItem.objects.filter(plan=plan).order_by("-is_headline", "order", "pk"))
        for i, it in enumerate(items):
            if it.order != i:
                it.order = i
                it.save(update_fields=["order"])
        if plan.plan_type == "sport":
            PlanItem.objects.filter(plan=plan, is_headline=True).update(is_headline=False)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0089_split_squat_warmup_15_reps"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="planitem",
            options={"ordering": ["order", "pk"]},
        ),
        migrations.RunPython(renumber_and_clear, migrations.RunPython.noop),
    ]
