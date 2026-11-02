"""Flexiones anchas (wide push-up), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones. SIN cara (ni nariz ni ojo ni oreja).
La app usa el MISMO contador que las flexiones normales (slug wide-push-up, migracion 0100, counter_key "pushup", processPushup en workout.js):
de perfil solo mide el codo (hombro-codo-muñeca), asi que el gesto es identico; lo que cambia (manos MAS ABIERTAS que los hombros) no se ve de
perfil, y por eso el GIF lleva un recuadro gris "visto desde arriba" (como fondos / commando) con las manos separadas.
  - ARRIBA: codo >= PUSHUP_UP_ANGLE_DEG = 160 (armar >= 145), cuerpo recto (hombro-cadera-tobillo >= PUSHUP_LINE_MIN_DEG = 150), tumbado
    (inclinacion hombro-cadera <= ON_GROUND_MAX_TILT_DEG = 40), codos HACIA ATRAS,
  - ABAJO: codo <= PUSHUP_DOWN_ANGLE_DEG = 90 (cuenta con <= 100); cuenta al volver arriba (>= 130); manos y pies NO se mueven.
GIF de 4 fotogramas: arriba -> bajando (flecha gris abajo) -> abajo -> subiendo (flecha gris arriba). Al final se comprueban los umbrales (assert).
Uso: python ex_flexiones_anchas.py [carpeta_salida] [clave=valor ...]   (genera flexiones-anchas.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbM=118, elbB=64, hand_dx=0.0, far_dx=-0.03, foot=292, footF=296, far_t=1.5, headd=9, margin=0.32,
           arrows=1, arrow_dx=1.05, arrow_len=0.42, fingers=1, toe_x=0.0,
           inset=1, inset_x=0.80, inset_y=2.30, inset_s=1.15, hand_y=0.56, hand_back=0.0)
# elbA/elbM/elbB: angulo del codo (grados) arriba / a medio camino / abajo (la app: >=160 arriba, <=90 abajo; cuenta con <=100 y >=130)
# hand_dx: x de las manos respecto al hombro de ARRIBA (0 = justo debajo del hombro; <0 = algo por detras); far_dx: la mano lejana queda algo detras
# foot / footF: angulo del pie cercano / lejano (apoyo en las puntas: ~290 = punta hacia abajo); far_t: grados que la pierna lejana se separa de la cercana
# headd: grados que la cabeza mira por encima de la linea del cuerpo (cuello neutro, mirada al suelo un poco por delante)
# inset / inset_x / inset_y / inset_s: recuadro gris 'visto desde arriba' (inset=0 lo quita); hand_y: semiseparacion de las manos en el recuadro (0.30 = ancho de hombros);
# hand_back: cuanto quedan las manos por detras de la linea de hombros en el recuadro
# arrow_dx / arrow_len: posicion (delante de la cabeza) y largo de la flecha gris
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
PUSHUP_UP_ANGLE_DEG = 160
PUSHUP_DOWN_ANGLE_DEG = 90
PUSHUP_COUNT_DOWN_ANGLE_DEG = 100
PUSHUP_COUNT_UP_ANGLE_DEG = 130
PUSHUP_ARM_GATE_ANGLE_DEG = 145
PUSHUP_LINE_MIN_DEG = 150
ON_GROUND_MAX_TILT_DEG = 40
PUSHUP_BROKEN_TILT_DEG = 60

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo


def elbow_len(deg):
    """distancia hombro-muñeca para un angulo de codo dado"""
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


def pose_t(t, hip):
    """pose del cuerpo recto (tabla) con el tronco a t grados sobre la horizontal; las manos se ponen despues"""
    f1 = dict(f=1, ground=False, hip=hip, torso=t, head=t + CFG['headd'])
    legs = dict(near_leg=('fk', 180 + t, 180 + t, CFG['foot']),
                far_leg=('fk', 180 + t + CFG['far_t'], 180 + t + CFG['far_t'], CFG['footF']))
    return dict(f1, **legs, near_arm=('fk', 270, 0), far_arm=('fk', 270, 0))


def feet_low(J):
    """punto mas bajo de las piernas (con el mismo margen que figura.ground_shift)"""
    lows = []
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        lows += [k[1] - 0.13, he[1] - 0.04, to[1] - 0.04, a[1] - 0.07]
    return min(lows)


def toe_x(J):
    return min(J[s + '_leg'][4][0] for s in ('near', 'far'))


# ---- el cuerpo gira como una tabla alrededor de las puntas de los pies (que NO se mueven) ----
# tabla: inclinacion t del tronco -> posicion del hombro y de la cadera con los pies apoyados en el suelo y la punta en toe_x
_T = np.linspace(2, 50, 4801)
_S = []
for _t in _T:
    _J = build_side(pose_t(_t, (0.0, 0.0)))
    _dy = -feet_low(_J); _dx = CFG['toe_x'] - toe_x(_J)
    _S.append((_J['S'] + np.array([_dx, _dy]), (_dx, _dy)))

dA = elbow_len(CFG['elbA'])
shA = WY + dA                                  # ARRIBA: brazos casi rectos y VERTICALES (muñeca justo debajo del hombro)


def pose(t, hip, bend='cw'):
    p = pose_t(t, hip)
    p['near_arm'] = ('ik', (HX, WY), bend); p['far_arm'] = ('ik', (HXF, WY), bend)
    p['near_hand'] = HAND; p['far_hand'] = HAND
    return p


# ARRIBA: el hombro a la altura que da el codo casi recto
iA = min(range(len(_T)), key=lambda i: abs(_S[i][0][1] - shA))
assert abs(_S[iA][0][1] - shA) < 2e-3, 'no hay solucion de postura arriba'
tA, hipA = float(_T[iA]), _S[iA][1]
HX = _S[iA][0][0] + CFG['hand_dx']             # x de las manos (FIJAS)
HXF = HX + CFG['far_dx']                       # mano lejana, un pelin detras


def solve_elbow(elb):
    """t y cadera para que el codo (hombro-codo-muñeca) mida 'elb' grados con las manos en (HX, WY) y los pies fijos"""
    d = elbow_len(elb)
    cand = [i for i in range(len(_T)) if WY + 0.2 < _S[i][0][1] <= shA + 1e-6]
    i = min(cand, key=lambda i: abs(np.hypot(_S[i][0][0] - HX, _S[i][0][1] - WY) - d))
    assert abs(np.hypot(_S[i][0][0] - HX, _S[i][0][1] - WY) - d) < 4e-3, 'no hay solucion de postura para el codo %s' % elb
    return float(_T[i]), _S[i][1]


tM, hipM = solve_elbow(CFG['elbM'])
tB, hipB = solve_elbow(CFG['elbB'])
A, M, B = pose(tA, hipA), pose(tM, hipM), pose(tB, hipB)

for p_ in (A, M, B):
    J_ = build_side(p_)
    assert J_['near_arm'][1][0] < J_['S'][0] + 1e-6, 'el codo debe quedar detras del hombro (codos hacia atras), cambia ccw/cw'


def dedos(J):
    """rayitas de los dedos sobre la mano apoyada (la mano es un tubo corto; con ellas se lee la palma plana en el suelo)"""
    def f(pen):
        if not CFG['fingers']:
            return
        w_, tip = J['near_arm'][2], J['near_handtip']
        for k_ in (0.12, 0.20):
            x = tip[0] - k_
            pen.line([(x, w_[1] + 0.045), (x, w_[1] + 0.085)], w=pen.c.LI * 0.8)
    return f


def flecha(bajando, y0, y1, x):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (y0 + y1) / 2; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (x, a), (x, b))
    return f


def vista_cenital():
    """Recuadro gris 'visto desde arriba' (como en fondos / commando): de perfil no se ve donde van las manos, aqui si.
    Cabeza a la derecha, linea de hombros, brazos hasta las manos (circulos) y, en gris punteado, donde irian las manos en una flexion normal."""
    k_ = CFG['inset_s']; cx, cy, hw, hh = CFG['inset_x'], CFG['inset_y'], 0.95 * k_, 0.72 * k_
    sx, sw = cx - 0.10 * k_, 0.30 * k_                         # x de los hombros y semiancho de hombros
    hxx, hy = sx - CFG['hand_back'] * k_, CFG['hand_y'] * k_   # x de las manos y semiseparacion entre ellas (desde el eje del cuerpo)

    def f(pen):
        if not CFG['inset']:
            return
        pen.line([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh), (cx - hw, cy - hh)], w=pen.c.LI * 0.8, col=FLOOR)
        pen.line([(sx, cy - sw), (sx, cy + sw)], w=pen.c.LW * 0.9)                         # hombros
        pen.line([(sx, cy), (cx - hw + 0.12 * k_, cy)], w=pen.c.LI * 0.9, col=GREY_ARROW)  # cuerpo (hacia los pies)
        pen.paint([('c', (sx + 0.34 * k_, cy), 0.15 * k_)])                                # cabeza
        for sg in (1, -1):                                                                 # manos normales (fantasma, punteado gris)
            th = np.linspace(0, 2 * np.pi, 48); r = 0.07 * k_
            for a0 in range(0, 48, 6):
                seg = [(sx + r * np.cos(t), cy + sg * sw + r * np.sin(t)) for t in th[a0:a0 + 3]]
                pen.line(seg, w=pen.c.LI * 0.8, col=GREY_ARROW)
        for sg in (1, -1):                                                                 # brazos (hombro -> mano)
            pen.line([(sx, cy + sg * sw), (hxx, cy + sg * hy)], w=pen.c.LI * 0.9, col=GREY_ARROW)
        pass
        for sg in (1, -1):
            pen.paint([('c', (hxx, cy + sg * hy), 0.07 * k_)])                             # manos
    return f


JA, JM, JB = build_side(A), build_side(M), build_side(B)
ax = JA['hd'][0] + CFG['arrow_dx']
ex = lambda J, extra: [dedos(J), vista_cenital()] + extra
# encuadre fijo para los 4 fotogramas (flecha incluida)
bb = (ax - 0.15, 0.0, ax + 0.15, JA['hd'][1] + 0.4)
if CFG['inset']:
    k_ = CFG['inset_s']; bb = (min(bb[0], CFG['inset_x'] - 1.0 * k_), bb[1], max(bb[2], CFG['inset_x'] + 1.0 * k_), max(bb[3], CFG['inset_y'] + 0.8 * k_))
imgs = render_scene([A, M, B, M], OUT + 'flexiones-anchas', durations=[1200, 700, 1300, 700], margin=CFG['margin'], bbox_extra=bb,
                    extras=[ex(JA, []), ex(JM, [flecha(True, JB['S'][1], JA['S'][1], ax)]), ex(JB, []),
                            ex(JM, [flecha(False, JB['S'][1], JA['S'][1], ax)])])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def codo(J, sd):
    sh, e, w_ = J[sd + '_arm']; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def tilt(J):
    d = J['H'] - J['S']
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


for nombre, J in (('arriba', JA), ('a medio camino', JM), ('abajo', JB)):
    print(f"{nombre:15s}: codo {codo(J,'near'):.0f}° | linea hombro-cadera-tobillo {ang3(J['S'], J['H'], J['near_leg'][2]):.0f}° | "
          f"inclinacion {tilt(J):.0f}° | hombro a y={J['S'][1]:.2f} | codo {J['near_arm'][1][0]-J['S'][0]:+.2f} en x respecto al hombro | "
          f"muñeca ({J['near_arm'][2][0]:.2f}, {J['near_arm'][2][1]:.2f})")
assert codo(JA, 'near') >= PUSHUP_UP_ANGLE_DEG and codo(JA, 'far') >= PUSHUP_UP_ANGLE_DEG, 'arriba: el codo debe estar casi recto (>=160)'
assert codo(JB, 'near') <= PUSHUP_DOWN_ANGLE_DEG and codo(JB, 'far') <= PUSHUP_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar a <=90'
assert PUSHUP_COUNT_DOWN_ANGLE_DEG < codo(JM, 'near') < PUSHUP_UP_ANGLE_DEG, 'a medio camino: entre los dos umbrales'
for J in (JA, JM, JB):
    assert ang3(J['S'], J['H'], J['near_leg'][2]) >= PUSHUP_LINE_MIN_DEG, 'el cuerpo debe quedar en linea recta (hombro-cadera-tobillo >= 150)'
    assert tilt(J) <= ON_GROUND_MAX_TILT_DEG, 'tumbado de verdad: inclinacion hombro-cadera <= 40'
    assert tilt(J) < PUSHUP_BROKEN_TILT_DEG
    assert np.allclose(J['near_arm'][2], JA['near_arm'][2], atol=1e-6), 'las manos no se mueven'
    assert abs(feet_low(J)) < 3e-3, 'los pies deben tocar el suelo'
    assert J['near_leg'][4][0] == JA['near_leg'][4][0] or abs(J['near_leg'][4][0] - JA['near_leg'][4][0]) < 2e-3, 'los pies no se mueven'
assert abs(HXF - HX) <= 0.1, 'las dos manos deben quedar casi a la misma x (de perfil se tapan)'
print('OK: arriba, abajo y a medio camino coinciden con los umbrales del contador (pushup, el mismo que flexiones)')
