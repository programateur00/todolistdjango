"""Dominadas con salto (jumping pull-up), vista FRONTAL, agarre prono algo mas ancho que los hombros.
Misma escena (barra + postes), muñeco y vista que ex_dominadas.py (dominadas normales: la app usa el MISMO contador
"pullup", slug jumping-pullup). Cambia el arranque: la barra queda mas baja (se alcanza de pie) y se empieza con los
PIES EN EL SUELO, rodillas flexionadas y los brazos estirados agarrados a la barra (muñecas por encima de los hombros,
que es lo que pide el contador para armar). De ahi se salta y se tira: arriba la barbilla pasa la barra con el codo
doblado y los pies ya en el aire. Una flecha gris indica el impulso del salto.
Uso: python ex_dominadas_salto.py [carpeta_salida] [clave=valor ...]   (genera dominadas-con-salto.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(bar=3.80, grip=0.60, top_dy=0.26, head=90, shin=0.55, out=1, margin=0.5, post=1.25,
           ankle_y=0.20, arm_bend=1.14, knee_out=16, shin_in=5, arrows=1)   # ankle_y: altura de los tobillos con los pies en el suelo; arm_bend: distancia hombro-barra en vertical con los brazos (casi) estirados
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

BAR = CFG['bar']; P = CFG['post']
RIG = [('bar', BAR, -P, P), ('post', -P, 0.0, BAR + 0.25), ('post', P, 0.0, BAR + 0.25)]
g = CFG['grip']
bR, bL = ('cw', 'ccw') if CFG['out'] else ('ccw', 'cw')   # codos hacia fuera / hacia dentro


def pose(hip_y, shrug=0.0, head=90, **kw):
    return dict(view='front', ground=False, hip=(0, hip_y), torso=90, head=head, shrug=shrug,
                R_arm=('ik', (g, BAR), bR), L_arm=('ik', (-g, BAR), bL), **kw)


# A: abajo = de pie en cuclillas, PIES EN EL SUELO, rodillas flexionadas (en la vista frontal el muslo se ve acortado y las
#    rodillas salen un pelin hacia fuera), brazos estirados agarrados a la barra
ko, si = CFG['knee_out'], CFG['shin_in']                              # muslo hacia fuera 'ko' grados; la espinilla vuelve hacia dentro 'si' grados (pies a la anchura de las caderas)
hipA = BAR - 1.0 - CFG['arm_bend']                                   # cadera: la que deja los brazos casi estirados agarrados a la barra
thA = ((hipA - CFG['ankle_y']) - L_SHIN * np.cos(np.deg2rad(si))) / (L_THIGH * np.cos(np.deg2rad(ko)))   # escorzo del muslo para que los tobillos queden pegados al suelo
legsA = dict(R_leg=('fk', 270 + ko, 270 - si), L_leg=('fk', 270 - ko, 270 + si), thigh_R=thA, thigh_L=thA)
A = pose(hipA, **legsA)
# B: arriba = barbilla por encima de la barra, ya en el aire: piernas colgando con las rodillas dobladas hacia atras
legsB = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268), shin_R=CFG['shin'], shin_L=CFG['shin'])
B = pose(BAR - CFG['top_dy'] - 1.0, head=CFG['head'], **legsB)


def manos(pose_):
    """Manos agarrando la barra (agarre prono visto de frente): la barra por delante de la palma y los dedos rodeandola."""
    J = build_front(pose_); hs = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        hs.append(w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05)   # mismo centro que la mano que dibuja figura.py
    return [lambda pen, h=h: draw_grip_front(pen, h, BAR) for h in hs]


def flechas(pen):
    """Flechas grises hacia arriba a los lados del cuerpo: impulso del salto."""
    if not CFG['arrows']:
        return
    for sg in (1, -1):
        draw_line_arrow(pen, (sg * 0.92, 0.95), (sg * 0.92, 1.95))


render_scene([A, B], OUT + 'dominadas-con-salto', props=RIG, durations=[1200, 1200], margin=CFG['margin'],
             extras=[manos(A) + [flechas], manos(B)])
