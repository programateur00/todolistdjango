import sys; sys.path.insert(0, '/tmp/claude-0/work')
from figura import *

OUT = '/tmp/claude-0/work/out/'
which = sys.argv[1:]  # nombres a generar (vacío = todos)


def want(n):
    return (not which) or n in which


HEAD_BEHIND = lambda b1, b2: dict(near_arm=('ikh', -0.05, -0.10, b1), far_arm=('ikh', -0.05, -0.10, b2))

# ------------------------------------------------------------------ CRUNCH
if want('crunch'):
    legs = dict(near_leg=('fk', 125, 250, 180), far_leg=('fk', 118, 245, 180))
    base = dict(f=-1, hip=(0, 0.3), **legs, **HEAD_BEHIND('ccw', 'cw'))
    render_scene([dict(base, torso=0), dict(base, torso=38, head=44)], OUT + 'crunch')

# ------------------------------------------------------------------ DOUBLE CRUNCH
if want('double-crunch'):
    A = dict(f=-1, hip=(0, 0.3), torso=14, head=20, near_leg=('fk', 163, 163, 90), far_leg=('fk', 160, 160, 90), **HEAD_BEHIND('ccw', 'cw'))
    B = dict(f=-1, hip=(0, 0.3), torso=58, head=64, near_leg=('fk', 108, 218, 150), far_leg=('fk', 112, 222, 150), **HEAD_BEHIND('ccw', 'cw'))
    render_scene([A, B], OUT + 'double-crunch')

# ------------------------------------------------------------------ LEG RAISES
if want('leg-raise'):
    arms = dict(near_arm=('fk', 183, 183), far_arm=('fk', 186, 186))
    A = dict(f=-1, hip=(0, 0.3), torso=0, head=0, near_leg=('fk', 183, 183, 90), far_leg=('fk', 185, 185, 90), **arms)
    B = dict(f=-1, hip=(0, 0.3), torso=0, head=0, near_leg=('fk', 95, 95, 5), far_leg=('fk', 98, 98, 5), **arms)
    render_scene([A, B], OUT + 'leg-raise')

# ------------------------------------------------------------------ TIJERITAS (scissor kick)
if want('scissor-kick'):
    arms = dict(near_arm=('fk', 183, 183), far_arm=('fk', 186, 186))
    A = dict(f=-1, hip=(0, 0.3), torso=3, head=10, near_leg=('fk', 147, 147, 90), far_leg=('fk', 172, 172, 90), **arms)
    B = dict(f=-1, hip=(0, 0.3), torso=3, head=10, near_leg=('fk', 172, 172, 90), far_leg=('fk', 147, 147, 90), **arms)
    render_scene([A, B], OUT + 'scissor-kick', durations=[700, 700])

# ------------------------------------------------------------------ MUAY THAI (balanceo de pierna)
if want('muay-thai'):
    A = dict(f=1, hip=(0, 2), torso=90, near_leg=('fk', 268, 268, 0), far_leg=('fk', 272, 272, 0),
             near_arm=('fk', 268, 285), far_arm=('fk', 272, 292))
    B = dict(f=1, hip=(0, 2), torso=96, head=94, near_leg=('fk', 18, 14, 60), far_leg=('fk', 272, 272, 0),
             near_arm=('fk', 238, 252), far_arm=('fk', 25, 38))
    render_scene([A, B], OUT + 'muay-thai', durations=[900, 1100])
