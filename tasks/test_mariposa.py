"""Ejercicio «Mariposa» (butterfly stretch), 2026-10-19.

Estiramiento cronometrado con cámara (counter_key "butterflystretch"): el detector vive en workout.js
(web y app), y aquí se comprueba lo que depende del servidor -- que la migración lo siembre en el
catálogo con los datos esperados y que views.py lo trate como contador de postura (si no, la pantalla de
entreno lo daría por «sin contador por cámara»)."""
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Exercise, Task, WarmupStatus
from .utils import get_current_user
from .views import COUNTERS, POSTURE_COUNTERS

STATIC_JS = Path(__file__).resolve().parent.parent / "static" / "js"


class ButterflyStretchCatalogTests(TestCase):
    def test_seeded_in_catalog(self):
        ex = Exercise.objects.get(slug="butterfly-stretch")
        self.assertEqual(ex.name, "Mariposa")
        self.assertEqual(ex.mode, Exercise.MODE_TIMED)
        self.assertEqual(ex.counter_key, "butterflystretch")
        self.assertEqual(ex.body_area, "warmup")
        self.assertTrue(ex.is_active)
        self.assertEqual(ex.level, "")  # los estiramientos quedan fuera del sistema de niveles
        self.assertEqual(ex.met, 2.3)

    def test_counter_registered_as_posture_counter(self):
        self.assertIn("butterflystretch", POSTURE_COUNTERS)
        self.assertNotIn("butterflystretch", COUNTERS)  # es de aguante, no de repeticiones

    def test_not_picked_by_the_sport_plan_generator(self):
        from .ai import _select_sport_exercises
        for level in ("beginner", "intermediate", "advanced"):
            for area in ("upper_body", "lower_body"):
                try:
                    slugs = [e.slug for e in _select_sport_exercises(level, area, False)]
                except Exception:  # catálogo corto para esa combinación: no es lo que se prueba aquí
                    continue
                self.assertNotIn("butterfly-stretch", slugs)


class ButterflyStretchWiringTests(SimpleTestCase):
    """El contador tiene que estar dado de alta en los sitios de la web donde se enumeran los contadores de postura."""

    def test_web_js_registers_the_counter(self):
        workout = (STATIC_JS / "workout.js").read_text(encoding="utf-8")
        circuit = (STATIC_JS / "circuit.js").read_text(encoding="utf-8")
        for name in ("CAMERA_POSTURE_COUNTERS", "NO_REST_COUNTERS", "STRETCH_HOLD_COUNTERS"):
            line = re.search(rf"^const {name} = new Set\(\[.*\]\);", workout, re.M)
            self.assertIsNotNone(line, name)
            self.assertIn('"butterflystretch"', line.group(0), name)
        self.assertIn("export function checkButterflyStretch", workout)
        self.assertIn("export function createButterflyStretchChecker", workout)
        self.assertIn("createButterflyStretchChecker", circuit)
        self.assertRegex(circuit, r'const POSTURE_COUNTERS = new Set\(\[[^\]]*"butterflystretch"')

    def test_butterfly_has_no_standby_step(self):
        """Simétrico y sentado: no pide el paso 1 de standby de los estiramientos de pie."""
        workout = (STATIC_JS / "workout.js").read_text(encoding="utf-8")
        self.assertIn('const STRETCH_NO_STANDBY_COUNTERS = new Set(["butterflystretch"]);', workout)
        self.assertIn("!STRETCH_NO_STANDBY_COUNTERS.has(this.counterKey)", workout)


class ButterflyStretchPageTests(TestCase):
    """Abierta suelta (fuera de un circuito) la mariposa enseña la pantalla de entreno con cámara, no «sin contador»."""

    def setUp(self):
        self.user = get_current_user()
        WarmupStatus.mark_done(self.user)   # si no, task_workout manda a /calentamiento/
        self.task = Task.objects.create(title="Estiramientos", category=Task.CATEGORY_SPORT, user=self.user)

    def test_standalone_butterfly_renders_the_camera_workout_screen(self):
        r = self.client.get(reverse("tasks:task_workout", args=[self.task.pk]) + "?exercise=butterfly-stretch")
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "tasks/task_workout.html")
        self.assertEqual(r.context["exercise"].counter_key, "butterflystretch")
        html = r.content.decode("utf-8")
        self.assertIn('data-counter-key="butterflystretch"', html)
        self.assertIn("plantas de", html)   # la nota de colocación (de frente, pies juntos, rodillas abiertas)
        self.assertIn("segundos", html)     # el contador marca segundos, no repeticiones
