"""Dominadas de arquero (archer pull-up), vista FRONTAL, agarre prono MUY ancho.
Misma escena (barra + postes), muñeco y vista que ex_dominadas.py / ex_dominadas_anchas.py. La app usa su propio
contador "archerpullup" (slug archer-pullup, processArcherPullup en workout.js), que pide de FRENTE a la cámara:
  - abajo: colgado con los brazos estirados (muñecas por encima de los hombros),
  - arriba (nariz a la altura de la barra): UN brazo doblado a ~90° (el que tira, ARCHER_BENT_MAX_DEG = 115°) y el
    OTRO totalmente estirado (el que se desliza por la barra, ARCHER_STRAIGHT_MIN_DEG = 150°),
  - se alterna de lado en cada repetición (la app avisa si haces dos seguidas al mismo lado).
Por eso el GIF tiene 4 fotogramas: colgado -> arriba tirando con la derecha -> colgado -> arriba tirando con la izquierda.
El cuerpo queda RECTO (tronco vertical, hombros a nivel, como en una dominada normal): solo se desplaza un poco hacia la
mano que tira. La geometria se RESUELVE (no se dibuja a ojo): con las manos muy abiertas, el desplazamiento lateral y la
altura de los hombros que dejan el brazo que tira a ~90° y el contrario casi recto salen de dos ecuaciones. Al final se
comprueban los angulos de codo contra los umbrales del contador.
Uso: python ex_dominadas_arquero.py [carpeta_salida] [clave=valor ...]   (genera dominadas-de-arquero.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
CFG = dict(grip=1.30, bend_d=0.85, straight=0.985, head=86, shin=0.55, out=1, margin=0.5, post=1.70)
# grip: manos MUY por encima del ancho de hombros (anchas = 1.05); bend_d: distancia hombro-muñeca del brazo que tira
# (0.835 = codo a 90 grados); straight: fraccion del brazo estirado (1 = recto del todo)
# head: direccion de la cabeza (grados) cuando tira con la derecha (con la izquierda se espeja); 90 = recta, <90 = hacia la mano que tira
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

ARCHER_BENT_MAX_DEG, ARCHER_STRAIGHT_MIN_DEG = 115, 150   # mismos umbrales que workout.js
SW = 0.34                                                  # medio ancho de hombros (build_front, 'shoulder_w')
REACH = L_UA + L_FA

P = CFG['post']; g = CFG['grip']
RIG = [('bar', BAR, -P, P), ('post', -P, 0.0, BAR + 0.25), ('post', P, 0.0, BAR + 0.25)]
bR, bL = ('cw', 'ccw') if CFG['out'] else ('ccw', 'cw')   # codos hacia fuera / hacia dentro
legs = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268), shin_R=CFG['shin'], shin_L=CFG['shin'])


def pose(hip, torso=90, head=90, **kw):
    return dict(view='front', ground=False, hip=hip, torso=torso, head=head, shrug=0.0,
                R_arm=('ik', (g, BAR), bR), L_arm=('ik', (-g, BAR), bL), **legs, **kw)


# A: colgado con los dos brazos (casi) estirados en V abierta (abajo)
dyA = np.sqrt((CFG['straight'] * REACH) ** 2 - (g - SW) ** 2)
A = pose((0, BAR - 1.0 - dyA))


def arriba(s):
    """Arriba tirando con el brazo derecho (s=+1) o el izquierdo (s=-1), con el tronco vertical y los hombros a nivel.
    Incognitas: desplazamiento lateral x del cuerpo hacia la mano que tira y altura dy de los hombros bajo la barra:
      (g - x - SW)^2 + dy^2 = bend_d^2      (brazo que tira, ~90 grados)
      (g + x - SW)^2 + dy^2 = (straight*REACH)^2   (brazo estirado, casi recto)"""
    S_, B_ = CFG['straight'] * REACH, CFG['bend_d']
    x = (S_ ** 2 - B_ ** 2) / (4 * (g - SW))
    dy = np.sqrt(B_ ** 2 - (g - x - SW) ** 2)
    p = pose((s * x, BAR - dy - 1.0), torso=90, head=CFG['head'] if s > 0 else 180 - CFG['head'])
    return p, (x, dy)


B1, (dx_, dy_) = arriba(+1)
B2, _ = arriba(-1)


def codo(J, sd):
    sh, e, w_ = J[sd + '_arm']; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


# comprobacion contra el contador: el que tira <= 115 grados, el estirado >= 150, y las dos muñecas EN la barra
for nombre, Bp, tira, estira in (('derecha', B1, 'R', 'L'), ('izquierda', B2, 'L', 'R')):
    J = build_front(Bp)
    et, ee = codo(J, tira), codo(J, estira)
    ok = et <= ARCHER_BENT_MAX_DEG and ee >= ARCHER_STRAIGHT_MIN_DEG
    for sd, hx in (('R', g), ('L', -g)):
        assert np.linalg.norm(J[sd + '_arm'][2] - np.array([hx, BAR])) < 0.02, f'muñeca {sd} fuera de la barra'
    print(f'tira con la {nombre}: codo que tira {et:.0f}° (<= {ARCHER_BENT_MAX_DEG}), codo estirado {ee:.0f}° (>= {ARCHER_STRAIGHT_MIN_DEG}) -> '
          f'{"OK" if ok else "FUERA DE UMBRAL"}; desplazamiento lateral {dx_:.2f} (tronco vertical), hombros a {dy_:.2f} de la barra')
    assert ok
JA = build_front(A)
print(f'abajo: codos {codo(JA, "R"):.0f}° / {codo(JA, "L"):.0f}°, muñecas por encima de los hombros: {JA["R_arm"][2][1] > JA["R_arm"][0][1]}')


def manos(pose_):
    """Manos agarrando la barra (agarre prono visto de frente): la barra por delante de la palma y los dedos rodeandola."""
    J = build_front(pose_); hs = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        hs.append(w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05)   # mismo centro que la mano que dibuja figura.py
    return [lambda pen, h=h: draw_grip_front(pen, h, BAR) for h in hs]


render_scene([A, B1, A, B2], OUT + 'dominadas-de-arquero', props=RIG, durations=[1000, 1300, 1000, 1300], margin=CFG['margin'],
             extras=[manos(A), manos(B1), manos(A), manos(B2)])
