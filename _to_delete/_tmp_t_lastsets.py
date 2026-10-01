from django.test import TestCase
from django.contrib.auth import get_user_model
from tasks.models import Plan, PlanItem, Exercise, WorkoutSession

class LastSetsTest(TestCase):
    def test_all_progressions(self):
        U = get_user_model()
        u = U.objects.create_user("a", password="x")
        ex = Exercise.objects.filter(mode=Exercise.MODE_POSE).first()
        self.assertIsNotNone(ex)
        plan = Plan.objects.create(user=u, name="p")
        for prog in (PlanItem.PROG_FAILURE, PlanItem.PROG_COMPLETION):
            it = PlanItem.objects.create(plan=plan, exercise=ex, progression=prog)
            self.assertIsNone(it.last_session_set_reps())
        WorkoutSession.objects.create(user=u, plan=plan, exercise=ex.slug, sets=[{"reps": 5}, {"reps": 3}])
        for it in plan.items.all():
            self.assertEqual(it.last_session_set_reps(), [5, 3], it.progression)
