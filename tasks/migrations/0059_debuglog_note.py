from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0058_debuglog"),
    ]

    operations = [
        migrations.AddField(
            model_name="debuglog",
            name="note",
            field=models.TextField(blank=True),
        ),
    ]
