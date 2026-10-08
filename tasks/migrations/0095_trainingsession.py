import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0094_ilerna_study_source'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_seconds', models.PositiveIntegerField(default=0)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('plan', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='training_sessions', to='tasks.plan')),
                ('routine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='training_sessions', to='tasks.routine')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='training_sessions', to='tasks.task')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='training_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-recorded_at'],
            },
        ),
        migrations.AddField(
            model_name='workoutsession',
            name='training_session',
            field=models.ForeignKey(blank=True, help_text='Sesión completa (con su cronómetro total) a la que pertenece este ejercicio.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workouts', to='tasks.trainingsession'),
        ),
    ]
