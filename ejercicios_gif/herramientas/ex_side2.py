import sys; sys.path.insert(0, '/tmp/claude-0/work')
from figura import *

OUT = '/tmp/claude-0/work/out/'
which = sys.argv[1:]


def want(n):
    return (not which) or n in which


def solve_theta(make_pose, lo, hi, n=800):
    """Ángulo de torso/piernas para que el punto más bajo de los pies toque y=0 (con S fijo)."""
    best = None
    for th in np.linspace(lo, hi, n):
        J = build_side(make_pose(th))
        low = min(min(J[s + '_leg'][3][1], J[s + '_leg'][4][1]) - 0.04 for s in ('near', 'far'))
        err = abs(low - J['S'][1] * 0)  # S.y fijo, suelo en 0
        if best is None or err < best[0]:
            best = (err, th)
    return best[1]


# ------------------------------------------------------------------ PLANCHA (antebrazos)
if want('plank'):
    def plank_pose(th, Sy=0.82, Sx=0.0, arms=None):
        return dict(f=1, sh=(Sx, Sy), torso=th, head=th - 4,
                    near_leg=('fk', 180 + th, 180 + th, 235), far_leg=('fk', 180 + th, 180 + th, 235),
                    near_arm=('fk', 270, 0), far_arm=('fk', 268, 3))
    thB = solve_theta(lambda th: plank_pose(th), 0, 40)
    B = plank_pose(thB)
    # A: tumbado, caderas en el suelo, apoyado en antebrazos (inicio)
    def lying_pose(th, Sy=0.42):
        return dict(f=1, sh=(0.0, Sy), torso=th, head=th + 8,
                    near_leg=('fk', 180 + th, 180 + th, 235), far_leg=('fk', 180 + th, 180 + th, 235),
                    near_arm=('ik', (0.70, 0.10), 'cw'), far_arm=('ik', (0.73, 0.10), 'cw'))
    thA = solve_theta(lambda th: lying_pose(th), 0, 40)
    A = lying_pose(thA)
    print('plank th', thA, thB)
    render_scene([A, B], OUT + 'plank', durations=[1000, 1400])

# ------------------------------------------------------------------ FONDOS (dips) en paralelas
if want('dips'):
    yb = 2.0
    legs = dict(near_leg=('fk', 258, 178, 250), far_leg=('fk', 262, 182, 250))
    A = dict(f=1, ground=False, sh=(0.0, yb + 1.18), torso=84, head=88, near_arm=('fk', 270, 270), far_arm=('fk', 268, 268), **legs)
    B = dict(f=1, ground=False, sh=(0.08, yb + 0.72), torso=66, head=72, near_arm=('ik', (0.0, yb), 'cw'), far_arm=('ik', (0.0, yb), 'cw'), **legs)
    props = [('bar', yb - 0.0, -0.55, 0.40), ('post', -0.42, 0.0, yb), ('floorbar', -1.0, 0.0, 0.2, 0.0)]
    render_scene([A, B], OUT + 'dips', props=props, y_floor=0.0)

# ------------------------------------------------------------------ BURPEES
if want('burpee'):
    stand = dict(f=1, hip=(0, 1.98), torso=90, near_leg=('fk', 268, 268, 0), far_leg=('fk', 272, 272, 0),
                 near_arm=('fk', 268, 285), far_arm=('fk', 272, 292))
    squat = dict(f=1, hip=(-0.36, 0.86), torso=26, head=40,
                 near_leg=('ik', (0.02, 0.12), 'ccw', 0), far_leg=('ik', (0.0, 0.12), 'ccw', 0),
                 near_arm=('ik', (0.78, 0.09), 'ccw'), far_arm=('ik', (0.70, 0.09), 'ccw'))

    def plank_arm(th, Sy):
        return dict(f=1, sh=(0.8, Sy), torso=th, head=th - 6,
                    near_leg=('fk', 180 + th, 180 + th, 245), far_leg=('fk', 180 + th, 180 + th, 245),
                    near_arm=('fk', 270, 270), far_arm=('fk', 268, 268))
    th = solve_theta(lambda t: plank_arm(t, 1.27), 0, 45)
    plank = plank_arm(th, 1.27)

    def pushdown(th, Sy):
        return dict(f=1, sh=(0.92, Sy), torso=th, head=th - 8,
                    near_leg=('fk', 180 + th, 180 + th, 245), far_leg=('fk', 180 + th, 180 + th, 245),
                    near_arm=('ik', (0.82, 0.09), 'cw'), far_arm=('ik', (0.80, 0.09), 'cw'))
    th2 = solve_theta(lambda t: pushdown(t, 0.62), 0, 45)
    down = pushdown(th2, 0.62)
    jump = dict(f=1, ground=False, hip=(0, 2.45), torso=90, head=92, near_leg=('fk', 262, 255, 280), far_leg=('fk', 266, 262, 290),
                near_arm=('fk', 82, 84), far_arm=('fk', 98, 96))
    render_scene([stand, squat, plank, down, jump], OUT + 'burpee', durations=[700, 700, 700, 700, 700], y_floor=0.0)

# ------------------------------------------------------------------ ELEPHANT STEPS (flexión adelante, rodillas alternas)
if want('elephant-steps-reps') or want('elephant-steps'):
    arms = dict(near_arm=('ik', (0.80, 0.09), 'ccw'), far_arm=('ik', (0.72, 0.09), 'ccw'))
    straight = ('fk', 280, 280, 0)
    base = dict(f=1, torso=322, head=300, **arms)
    A = dict(base, hip=(-0.34, 1.88), near_leg=('ik', (-0.12, 0.50), 'ccw', 285), far_leg=('fk', 280, 280, 0))
    B = dict(base, hip=(-0.34, 1.88), near_leg=('fk', 280, 280, 0), far_leg=('ik', (-0.12, 0.50), 'ccw', 285))
    if want('elephant-steps-reps'):
        render_scene([A, B], OUT + 'elephant-steps-reps', durations=[900, 900])
    if want('elephant-steps'):
        stand = dict(f=1, hip=(0, 1.98), torso=90, near_leg=('fk', 268, 268, 0), far_leg=('fk', 272, 272, 0),
                     near_arm=('fk', 268, 285), far_arm=('fk', 272, 292))
        fold = dict(base, hip=(-0.34, 1.98), near_leg=('fk', 280, 280, 0), far_leg=('fk', 282, 282, 0))
        render_scene([stand, fold], OUT + 'elephant-steps', durations=[900, 1300])
