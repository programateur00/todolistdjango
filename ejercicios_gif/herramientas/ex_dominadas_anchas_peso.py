"""Dominadas anchas con peso (wide-grip weighted pull-up), vista FRONTAL, agarre prono MUY por encima del ancho de hombros.
Combina las dos escenas ya hechas, sin tocar nada de ellas:
  - ex_dominadas_anchas.py: agarre ~3x el ancho de hombros (grip=1.05), postes mas separados, colgado mas alto (hipA) y arriba
    con los codos muy abiertos hacia fuera (la barbilla pasa la barra),
  - ex_dominadas_peso.py: el LASTRE (cinturon oscuro con hebilla en la cintura + cadena + disco de pesas entre los muslos),
    que sube y baja con el cuerpo colgando recto.
La app usa el MISMO contador "pullup" que dominadas / dominadas anchas / dominadas con peso (slug wide-weighted-pullup,
counter_key pullup, workout.js): abajo = colgado con las muñecas por encima de los hombros; arriba = nariz a la altura de la
barra (BAR_MARGIN_FACTOR) y codo (2D) <= PULLUP_TOP_ELBOW_MAX_DEG = 100 grados. Al final se comprueba que el fotograma de arriba
cumple ese umbral de codo y que las muñecas quedan EN la barra.
Uso: python ex_dominadas_anchas_peso.py [carpeta_salida] [clave=valor ...]   (genera dominadas-anchas-con-peso.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
CFG = dict(grip=1.05, hipA=2.38, top_dy=0.30, head=90, shin=0.55, out=1, margin=0.5, post=1.45,   # = ex_dominadas_anchas.py
           plate_r=0.25, ring_dy=0.34, belt_top=0.15)                                               # = ex_dominadas_peso.py (lastre)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

PULLUP_TOP_ELBOW_MAX_DEG = 100   # mismo umbral que workout.js

P = CFG['post']
RIG = [('bar', BAR, -P, P), ('post', -P, 0.0, BAR + 0.25), ('post', P, 0.0, BAR + 0.25)]
g = CFG['grip']
bR, bL = ('cw', 'ccw') if CFG['out'] else ('ccw', 'cw')   # codos hacia fuera / hacia dentro
legs = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268), shin_R=CFG['shin'], shin_L=CFG['shin'])

METAL = (104, 104, 104)      # gris oscuro del cinturon y del disco
SHINE = (232, 232, 232)      # lineas claras (hebilla, ranura del disco)


def pose(hip_y, shrug=0.0, head=90, **kw):
    return dict(view='front', ground=False, hip=(0, hip_y), torso=90, head=head, shrug=shrug,
                R_arm=('ik', (g, BAR), bR), L_arm=('ik', (-g, BAR), bL), **legs, **kw)


# A: colgado con los brazos estirados (abajo), en V abierta
A = pose(CFG['hipA'])
# B: barbilla por encima de la barra (arriba): el hombro queda a 'top_dy' de la barra
B = pose(BAR - CFG['top_dy'] - 1.0, head=CFG['head'])


def codo(J, sd):
    sh, e, w_ = J[sd + '_arm']; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


# comprobacion contra el contador: arriba codo <= 100 grados, abajo muñecas por encima de los hombros, y las muñecas EN la barra
# (abajo, con los brazos del todo estirados, la muñeca queda a ~0.02 de la barra: igual que en ex_dominadas_anchas.py, no se nota)
for nombre, Pp in (('abajo', A), ('arriba', B)):
    J = build_front(Pp)
    for sd, hx in (('R', g), ('L', -g)):
        assert np.linalg.norm(J[sd + '_arm'][2] - np.array([hx, BAR])) < 0.03, f'muñeca {sd} fuera de la barra ({nombre})'
    print(f'{nombre}: codos {codo(J, "R"):.0f}° / {codo(J, "L"):.0f}°, muñecas por encima de los hombros: '
          f'{J["R_arm"][2][1] > J["R_arm"][0][1] and J["L_arm"][2][1] > J["L_arm"][0][1]}')
JB = build_front(B)
assert max(codo(JB, 'R'), codo(JB, 'L')) <= PULLUP_TOP_ELBOW_MAX_DEG, 'arriba: el codo supera el umbral del contador'
assert min(codo(build_front(A), 'R'), codo(build_front(A), 'L')) > PULLUP_TOP_ELBOW_MAX_DEG, 'abajo: los brazos deben estar (casi) estirados'
print('OK: el fotograma de arriba cumple el umbral de codo del contador')


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


render_scene([A, B], OUT + 'dominadas-anchas-con-peso', props=RIG, durations=[1200, 1200], margin=CFG['margin'],
             extras=[manos(A) + lastre(A), manos(B) + lastre(B)])
