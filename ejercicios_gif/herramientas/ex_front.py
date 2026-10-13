import sys; sys.path.insert(0, '/tmp/claude-0/work')
from figura import *

OUT = '/tmp/claude-0/work/out/'
which = sys.argv[1:]


def want(n):
    return (not which) or n in which


BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
STAND = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268))
ARMS_DOWN = dict(R_arm=('fk', 281, 272), L_arm=('fk', 259, 268))

# ------------------------------------------------------------------ AGUANTE EN BARRA (dead hang)
if want('dead-hang'):
    grip = dict(R_arm=('ik', (0.52, BAR), 'ccw'), L_arm=('ik', (-0.52, BAR), 'cw'))
    A = dict(view='front', ground=False, hip=(0, 2.04), torso=90, **grip, **STAND)
    B = dict(view='front', ground=False, hip=(0, 2.22), torso=90, R_arm=('fk', 80, 87), L_arm=('fk', 100, 93),
             R_leg=('fk', 272, 262), L_leg=('fk', 268, 278), shin_R=0.32, shin_L=0.32)
    render_scene([A, B], OUT + 'dead-hang', props=RIG, durations=[1000, 1400])

# ------------------------------------------------------------------ DOMINADAS ESCAPULARES (de espaldas)
if want('scapular-pull'):
    mk = lambda hy, shrug: dict(view='front', ground=False, back=True, hip=(0, hy), torso=90, shrug=shrug,
                                R_arm=('ik', (0.58, BAR), 'ccw'), L_arm=('ik', (-0.58, BAR), 'cw'),
                                R_leg=('fk', 272, 272), L_leg=('fk', 268, 268))
    A = mk(2.04, 0.12)       # colgado pasivo, hombros encogidos hacia las orejas
    B = mk(2.24, -0.06)      # omóplatos bajados: el cuerpo sube un poco con los codos rectos
    def arrow(pen):
        draw_line_arrow(pen, (1.0, 2.6), (1.0, 3.1))
    render_scene([A, B], OUT + 'scapular-pull', props=RIG, durations=[1100, 1100], extras=[None, [arrow]])

# ------------------------------------------------------------------ CÍRCULOS DE BRAZOS
if want('arm-circles'):
    def pose(th):
        return dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', th, th), L_arm=('fk', 180 - th, 180 - th), **STAND)
    def arrows(pen):
        for sg in (1, -1):
            c = np.array([sg * 1.62, 3.14])
            draw_arrow(pen, c, 0.34, 140 if sg > 0 else 40, 430 if sg > 0 else -250) if False else None
    # flechas circulares junto a las manos (un circulo pequeño)
    def circ(pen):
        for sg, a0, a1 in ((1, 90, -200), (-1, 90, 380)):
            draw_arrow(pen, (sg * 1.78, 3.05), 0.26, a0, a1)
    frames = [pose(0), pose(32), pose(0), pose(-32)]
    render_scene(frames, OUT + 'arm-circles', durations=[450] * 4, extras=[[circ]] * 4)

# ------------------------------------------------------------------ TIJERAS DE BRAZOS
if want('arm-scissors'):
    A = dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', 4, 2), L_arm=('fk', 176, 178), **STAND)
    B = dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', 187, 190), L_arm=('fk', -7, -10), **STAND)
    C = dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', 4, 2), L_arm=('fk', 176, 178), **STAND)
    D = dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', -7, -10), L_arm=('fk', 187, 190), **STAND)
    # D invierte qué brazo va por encima: (R,L intercambiados en dibujo) -> se usa un cruce distinto
    render_scene([A, B, A, dict(B, R_arm=('fk', 170, 168), L_arm=('fk', 10, 12))], OUT + 'arm-scissors', durations=[600, 600, 600, 600])

# ------------------------------------------------------------------ ROTACIÓN DE CODOS (manos en los hombros)
if want('elbow-rotation'):
    down = dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', 276, 102), L_arm=('fk', 264, 78), **STAND)
    out = dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', 2, 130), L_arm=('fk', 178, 50), fore_R_fa=0.55, fore_L_fa=0.55, **STAND)
    up = dict(view='front', hip=(0, 2.0), torso=90, R_arm=('fk', 76, 250), L_arm=('fk', 104, 290), **STAND)
    def circ(pen):
        for sg, a0, a1 in ((1, 200, -90), (-1, -20, 270)):
            draw_arrow(pen, (sg * 1.12, 2.82), 0.30, a0, a1) if False else None
    arrows = lambda pen: [draw_arrow(pen, (1.15, 3.0), 0.28, 230, -20), draw_arrow(pen, (-1.15, 3.0), 0.28, -50, 200)]
    render_scene([down, out, up, out], OUT + 'elbow-rotation', durations=[500] * 4, extras=[[arrows]] * 4)

# ------------------------------------------------------------------ ROTACIÓN DE MUÑECAS (manos entrelazadas, de frente)
if want('wrist-rotation'):
    def pose(dx, dy):
        return dict(view='front', hip=(0, 2.0), torso=90,
                    R_arm=('ik', (0.05 + dx, 2.58 + dy), 'ccw'), L_arm=('ik', (-0.05 + dx, 2.58 + dy), 'cw'), **STAND)
    arrow = lambda pen: draw_arrow(pen, (0.0, 2.58), 0.36, 40, 330)
    r = 0.10
    render_scene([pose(0, r), pose(r, 0), pose(0, -r), pose(-r, 0)], OUT + 'wrist-rotation', durations=[450] * 4, extras=[[arrow]] * 4)

# ------------------------------------------------------------------ PINO: FLEXIONES (invertido, de frente)
if want('handstand-push-up'):
    legs = dict(R_leg=('fk', 83, 83), L_leg=('fk', 97, 97))
    A = dict(view='front', ground=False, hip=(0, 2.27), torso=270, head=270, R_arm=('fk', 262, 262), L_arm=('fk', 278, 278), **legs)
    B = dict(view='front', ground=False, hip=(0, 1.86), torso=270, head=272, R_arm=('ik', (-0.55, 0.09), 'cw'), L_arm=('ik', (0.55, 0.09), 'ccw'), **legs)
    render_scene([A, B], OUT + 'handstand-push-up', durations=[900, 900])

# ------------------------------------------------------------------ PLANCHA LATERAL (de frente, tumbado de lado)
if want('side-plank'):
    # B: caderas arriba, línea recta, apoyado en el antebrazo
    n = dv(74)
    legsB = dict(R_leg=('ik', (1.80, 0.38), 'ccw'), L_leg=('fk', 344, 344))
    B = dict(view='front', ground=False, hip=(0.0, 0.80), torso=164, head=164,
             R_arm=('fk', 92, 92), L_arm=('fk', 268, 350), fore_L_fa=0.4, **legsB)
    A = dict(view='front', ground=False, hip=(-0.25, 0.37), torso=135, head=140,
             R_arm=('fk', 92, 92), L_arm=('fk', 268, 350), fore_L_fa=0.4,
             R_leg=('fk', 358, 358), L_leg=('fk', 356, 356))
    render_scene([A, B], OUT + 'side-plank', durations=[1000, 1500])

# ------------------------------------------------------------------ TUCK LEVER (vista lateral, colgado e invertido)
if want('tuck-lever'):
    A = dict(f=1, ground=False, sh=(0.0, BAR - 1.18), torso=90, head=92, near_arm=('fk', 90, 90), far_arm=('fk', 92, 92),
             near_leg=('fk', 300, 238, 270), far_leg=('fk', 308, 244, 270))
    B = dict(f=-1, ground=False, hip=(0.0, BAR - 0.05), torso=280, head=276, near_arm=('fk', 82, 88), far_arm=('fk', 86, 90),
             near_leg=('fk', 40, 200, 260), far_leg=('fk', 52, 207, 260))
    props = [('bar', BAR, -0.9, 0.9)]
    render_scene([A, B], OUT + 'tuck-lever', props=props, durations=[1000, 1500], floor=False, margin=0.5)
