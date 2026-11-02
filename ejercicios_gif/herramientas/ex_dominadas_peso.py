"""Dominadas con peso (weighted pull-up), vista FRONTAL, agarre prono algo mas ancho que los hombros.
Misma escena, muñeco y movimiento que ex_dominadas.py (dominadas normales: la app usa el MISMO contador "pullup");
lo unico que cambia es el lastre: un CINTURON de lastre (banda oscura con hebilla en la cintura) del que cuelga una
cadena con un DISCO de pesas entre los muslos. El disco sube y baja con el cuerpo, colgando recto.
(Se elige cinturon y no chaleco porque deja a la vista torso y hombros, que son lo que mira la camara.)
Uso: python ex_dominadas_peso.py [carpeta_salida] [clave=valor ...]   (genera dominadas-con-peso.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
CFG = dict(grip=0.60, hipA=2.2, top_dy=0.26, head=90, shin=0.55, out=1, margin=0.5,
           plate_r=0.25, ring_dy=0.34, belt_top=0.15)   # disco: radio; ring_dy: bajada de la anilla de la cadena bajo la cadera
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

g = CFG['grip']
bR, bL = ('cw', 'ccw') if CFG['out'] else ('ccw', 'cw')   # codos hacia fuera / hacia dentro
legs = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268), shin_R=CFG['shin'], shin_L=CFG['shin'])

METAL = (104, 104, 104)      # gris oscuro del cinturon y del disco
SHINE = (232, 232, 232)      # lineas claras (hebilla, ranura del disco)


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


def lastre(pose_):
    """Cinturon de lastre (banda en la cintura + hebilla) y, colgando de el, cadena + disco entre los muslos."""
    H = build_front(pose_)['H']; hx, hy = float(H[0]), float(H[1])
    r = CFG['plate_r']; ring = np.array([hx, hy - CFG['ring_dy']])
    ctr = np.array([hx, ring[1] - 0.05 - r])                      # centro del disco (y del agujero por el que pasa la cadena)
    top = hy + CFG['belt_top']; bot = hy - 0.01                   # banda del cinturon: de la cintura a la cadera
    wt, wb = 0.295, 0.325                                         # media anchura arriba/abajo (un pelin mas que el pantalon)

    def belt(pen):
        c = pen.c
        pen.paint([('p', np.array([(hx - wt, top), (hx + wt, top), (hx + wb, bot), (hx - wb, bot)], float))], METAL)
        pen.line([(hx - 0.055, top - 0.03), (hx + 0.055, top - 0.03), (hx + 0.055, bot + 0.03), (hx - 0.055, bot + 0.03),
                  (hx - 0.055, top - 0.03)], w=c.LI * 0.9, col=SHINE)                    # hebilla
        for sg in (1, -1):                                                              # anillas D de las que sale la cadena
            pen.circ_px((hx + sg * (wb - 0.075), bot), c.LI * 1.6, SHINE)
            pen.circ_px((hx + sg * (wb - 0.075), bot), c.LI * 0.8, METAL)

    def chain(pen, p, q):
        c = pen.c; p = np.asarray(p, float); q = np.asarray(q, float); L = np.linalg.norm(q - p)
        pen.line([p, q], w=c.LI * 0.7)
        for t in np.linspace(0, 1, max(2, int(L / 0.05) + 1)):
            pen.circ_px(p + (q - p) * t, c.LI * 1.05, INK)

    def disco(pen):
        c = pen.c
        for sg in (1, -1):                                              # cadenas de la banda a la anilla (en V)
            chain(pen, (hx + sg * (wb - 0.075), bot), ring)
        chain(pen, ring, ctr)                                           # cadena hasta el agujero del disco
        pen.paint([('c', ctr, r)], METAL)                               # disco
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line([ctr + 0.74 * r * np.array([np.cos(a), np.sin(a)]) for a in th], w=c.LI * 0.8, col=SHINE)   # ranura del borde
        pen.paint([('c', ctr, 0.06)])                                   # agujero central
        pen.circ_px(ctr, c.LI * 1.4, INK)                               # extremo de la cadena (mosqueton)
        pen.circ_px(ring, c.LI * 1.9, INK)                              # anilla
        pen.circ_px(ring, c.LI * 0.8, WHITE)
    return [belt, disco]


render_scene([A, B], OUT + 'dominadas-con-peso', props=RIG, durations=[1200, 1200], margin=CFG['margin'],
             extras=[manos(A) + lastre(A), manos(B) + lastre(B)])
