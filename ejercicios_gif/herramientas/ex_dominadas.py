"""Dominadas (pull-up), vista FRONTAL, agarre prono algo más ancho que los hombros.
Mismo montaje (barra + postes) y vista que dead-hang de ex_front.py.
Uso: python ex_dominadas.py [carpeta_salida] [clave=valor ...]   (genera dominadas.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
CFG = dict(grip=0.60, hipA=2.2, top_dy=0.26, head=90, shin=0.55, out=1, margin=0.5)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

g = CFG['grip']
bR, bL = ('cw', 'ccw') if CFG['out'] else ('ccw', 'cw')   # codos hacia fuera / hacia dentro
legs = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268), shin_R=CFG['shin'], shin_L=CFG['shin'])


def pose(hip_y, shrug=0.0, head=90, **kw):
    return dict(view='front', ground=False, hip=(0, hip_y), torso=90, head=head, shrug=shrug,
                R_arm=('ik', (g, BAR), bR), L_arm=('ik', (-g, BAR), bL), **legs, **kw)


# A: colgado con los brazos estirados (abajo)
A = pose(CFG['hipA'])
# B: barbilla por encima de la barra (arriba): el hombro queda a 'top_dy' de la barra
B = pose(BAR - CFG['top_dy'] - 1.0, head=CFG['head'])


def manos(pose_):
    """Manos agarrando la barra (agarre prono visto de frente): la barra por delante de la palma y los dedos rodeandola."""
    J = build_front(pose_); hs = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        hs.append(w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05)   # mismo centro que la mano que dibuja figura.py
    return [lambda pen, h=h: draw_grip_front(pen, h, BAR) for h in hs]


render_scene([A, B], OUT + 'dominadas', props=RIG, durations=[1200, 1200], margin=CFG['margin'],
             extras=[manos(A), manos(B)])
