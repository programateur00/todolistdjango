"""Flexiones de rodillas declinadas (slug decline-knee-push-up, migracion 0101, counter_key "kneedeclinepushup"), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones / flexiones-inclinadas. SIN cara (ni nariz ni ojo ni oreja).
Como lo mira la app (workout.js: processKneePushup(lm, now, declined=true), KNEE_PUSHUP_*): de PERFIL, RODILLAS apoyadas en un banco/silla (espinilla doblada hacia arriba, 90 grados en la rodilla, tobillos en el aire) y manos en el suelo; mismo conteo de codo que
processPushup, cambia la comprobacion de postura:
  - cuerpo recto de la cabeza a las RODILLAS: hombro-cadera-rodilla >= KNEE_PUSHUP_LINE_MIN_DEG = 140 (>= 110 ya armado),
  - tobillos por encima de la rodilla: (rodilla.y - tobillo.y) / tronco >= KNEE_PUSHUP_MIN_ANKLE_RISE_FACTOR = 0.05 (piernas dobladas hacia arriba),
  - rodillas claramente por ENCIMA de las manos: (rodilla.y - muñeca.y) / tronco >= KNEE_DECLINE_PUSHUP_MIN_KNEE_RISE_FACTOR = 0.20 para armar
    (0.05 ya armado); aqui NO hay techo de inclinacion,
  - ARRIBA = brazos estirados (codo >= PUSHUP_UP_ANGLE_DEG = 160; para armar basta 145), CODOS HACIA ATRAS,
  - ABAJO: el codo se dobla hasta <= PUSHUP_DOWN_ANGLE_DEG = 90 (cuenta con <= 100); cuenta al volver arriba (>= 130); manos y rodillas NO se mueven:
    el cuerpo entero (recto como una tabla, muslo + tronco) gira alrededor de las rodillas.
Las piernas van dobladas 90 grados en la rodilla y el pie a 90 grados de la espinilla (como en crunch / fondos).
GIF de 4 fotogramas: arriba -> bajando (flecha gris abajo) -> abajo -> subiendo (flecha gris arriba). Al final se comprueban los umbrales (assert).
Uso: python ex_flexiones_rodillas_declinadas.py [carpeta_salida] [clave=valor ...]   (genera flexiones-de-rodillas-declinadas.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbM=118, elbB=64, hand_dx=0.0, far_dx=-0.07, footoff=0, far_t=1.5, headd=9, margin=0.32,
           arrows=1, arrow_dx=1.05, arrow_len=0.42, fingers=1, toe_x=0.0, bench=0.80, bench_w=1.0, bench_t=0.16, toe_gap=0.15)
# elbA/elbM/elbB: angulo del codo (grados) arriba / a medio camino / abajo (la app: >=160 arriba, <=90 abajo; cuenta con <=100 y >=130)
# hand_dx: x de las manos respecto al hombro de ARRIBA (0 = justo debajo del hombro; <0 = algo por detras); far_dx: la mano lejana queda algo detras
# footoff: grados extra del pie respecto a 90 con la espinilla (0 = pie a 90 grados de la espinilla, planta hacia arriba); far_t: grados que la pierna lejana se separa de la cercana
# headd: grados que la cabeza mira por encima de la linea del cuerpo (cuello neutro, mirada al suelo un poco por delante)
# bench: altura del banco donde se apoyan las rodillas (0 = rodillas en el suelo, sin banco); bench_w/bench_t: ancho y grosor; toe_gap: de la rodilla al borde delantero del banco (+0.10)
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
KNEE_PUSHUP_LINE_MIN_DEG = 140
KNEE_PUSHUP_MIN_ANKLE_RISE_FACTOR = 0.05
KNEE_DECLINE_PUSHUP_MIN_KNEE_RISE_FACTOR = 0.20
KNEE_DECLINE_PUSHUP_LOOSE_KNEE_RISE_FACTOR = 0.05
DECLINED = True

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo


def elbow_len(deg):
    """distancia hombro-muñeca para un angulo de codo dado"""
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


def pose_t(t, hip):
    """pose del cuerpo recto (tabla) con el tronco a t grados sobre la horizontal; las manos se ponen despues"""
    f1 = dict(f=1, ground=False, hip=hip, torso=t, head=t + CFG['headd'])
    legs = dict(near_leg=('fk', 180 + t, 90 + t, 180 + t + CFG['footoff']),
                far_leg=('fk', 180 + t + CFG['far_t'], 90 + t + CFG['far_t'], 180 + t + CFG['far_t'] + CFG['footoff']))
    return dict(f1, **legs, near_arm=('fk', 270, 0), far_arm=('fk', 270, 0))


def feet_low(J):
    """punto mas bajo de las piernas (con el mismo margen que figura.ground_shift)"""
    lows = []
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        lows += [k[1] - 0.13, he[1] - 0.04, to[1] - 0.04, a[1] - 0.07]
    return min(lows)


def toe_x(J):
    return min(J[s + '_leg'][1][0] for s in ('near', 'far'))        # x de la rodilla (el pivote)


# ---- el cuerpo gira como una tabla alrededor de las puntas de los pies (que NO se mueven) ----
# tabla: inclinacion t del tronco -> posicion del hombro y de la cadera con los pies apoyados en el suelo y la punta en toe_x
BH = CFG['bench']                            # y a la que quedan los pies (apoyados en el banco)
_T = np.linspace(-45, 45, 9001)
_S = []
for _t in _T:
    _J = build_side(pose_t(_t, (0.0, 0.0)))
    _dy = BH - feet_low(_J); _dx = CFG['toe_x'] - toe_x(_J)
    _S.append((_J['S'] + np.array([_dx, _dy]), (_dx, _dy)))

dA = elbow_len(CFG['elbA'])
shA = WY + float(np.sqrt(dA ** 2 - CFG['hand_dx'] ** 2))                                  # ARRIBA: brazos casi rectos y VERTICALES (muñeca justo debajo del hombro)


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
    cand = [i for i in range(len(_T)) if WY + 0.2 < _S[i][0][1] <= shA + 1e-6 and _T[i] <= tA + 1e-6]
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


JA, JM, JB = build_side(A), build_side(M), build_side(B)
ax = JA['hd'][0] + CFG['arrow_dx']
ex = lambda J, extra: [dedos(J)] + extra
# encuadre fijo para los 4 fotogramas (flecha incluida)
bb = (ax - 0.15, 0.0, ax + 0.15, JA['hd'][1] + 0.4)
# banco (detras del muñeco, como en fondos-en-banco): tapa con grosor y dos patas; las puntas de los pies apoyan encima
TOE_X = min(JA['near_leg'][1][0], JA['far_leg'][1][0])           # x de la rodilla
X_FRONT = TOE_X + CFG['toe_gap'] + 0.10                       # borde delantero del banco
X_BACK = X_FRONT - CFG['bench_w']
Y_TOP = BH - 0.055                                            # superficie (misma convencion que la linea del suelo: -0.055)
Y_BOT = Y_TOP - CFG['bench_t']
PROPS = None if BH <= 0 else [('floorbar', X_BACK, Y_TOP, X_FRONT, Y_TOP), ('floorbar', X_BACK, Y_BOT, X_FRONT, Y_BOT),
         ('floorbar', X_BACK, Y_TOP, X_BACK, Y_BOT), ('floorbar', X_FRONT, Y_TOP, X_FRONT, Y_BOT),
         ('floorbar', X_FRONT - 0.12, Y_BOT, X_FRONT - 0.12, -0.055), ('floorbar', X_BACK + 0.12, Y_BOT, X_BACK + 0.12, -0.055)]
# encuadre fijo para los 4 fotogramas (flecha incluida)
bb = (min(X_BACK - 0.1, ax - 0.15) if BH > 0 else ax - 0.15, -0.1, ax + 0.15, max(JA['hd'][1], JA['H'][1]) + 0.45)
imgs = render_scene([A, M, B, M], OUT + 'flexiones-de-rodillas-declinadas', props=PROPS, ground_all=False,
                    durations=[1200, 700, 1300, 700], margin=CFG['margin'], bbox_extra=bb,
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


def torso(J):
    return float(np.linalg.norm(J['S'] - J['H']))


for nombre, J in (('arriba', JA), ('a medio camino', JM), ('abajo', JB)):
    k_, w_, a_ = J['near_leg'][1], J['near_arm'][2], J['near_leg'][2]
    print(f"{nombre:15s}: codo {codo(J,'near'):.0f}° | linea hombro-cadera-rodilla {ang3(J['S'], J['H'], k_):.0f}° | rodilla (cadera-rodilla-tobillo) {ang3(J['H'], k_, a_):.0f}° | "
          f"tobillo sobre rodilla {(a_[1]-k_[1])/torso(J):.2f} torsos | rodilla sobre mano {(k_[1]-w_[1])/torso(J):.2f} torsos | inclinacion {tilt(J):.0f}° | "
          f"hombro a y={J['S'][1]:.2f} | codo {J['near_arm'][1][0]-J['S'][0]:+.2f} en x respecto al hombro")
assert codo(JA, 'near') >= PUSHUP_UP_ANGLE_DEG and codo(JA, 'far') >= PUSHUP_UP_ANGLE_DEG, 'arriba: el codo debe estar casi recto (>=160)'
assert codo(JB, 'near') <= PUSHUP_DOWN_ANGLE_DEG and codo(JB, 'far') <= PUSHUP_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar a <=90'
assert PUSHUP_COUNT_DOWN_ANGLE_DEG < codo(JM, 'near') < PUSHUP_UP_ANGLE_DEG, 'a medio camino: entre los dos umbrales'
for J in (JA, JM, JB):
    assert ang3(J['S'], J['H'], J['near_leg'][1]) >= KNEE_PUSHUP_LINE_MIN_DEG, 'cuerpo recto de la cabeza a las rodillas (hombro-cadera-rodilla >= 140)'
    assert abs(ang3(J['H'], J['near_leg'][1], J['near_leg'][2]) - 90) < 1.0, 'rodilla doblada 90 grados'
    for sd in ('near', 'far'):
        assert (J[sd + '_leg'][2][1] - J[sd + '_leg'][1][1]) / torso(J) >= KNEE_PUSHUP_MIN_ANKLE_RISE_FACTOR, 'tobillos por encima de las rodillas'
        if DECLINED:
            assert (J[sd + '_leg'][1][1] - J[sd + '_arm'][2][1]) / torso(J) >= KNEE_DECLINE_PUSHUP_MIN_KNEE_RISE_FACTOR, 'rodillas claramente mas altas que las manos (>= 0.20 torsos)'
    if not DECLINED:
        assert tilt(J) <= ON_GROUND_MAX_TILT_DEG, 'tumbado de verdad: inclinacion hombro-cadera <= 40'
        assert tilt(J) < PUSHUP_BROKEN_TILT_DEG
    assert np.allclose(J['near_arm'][2], JA['near_arm'][2], atol=1e-6), 'las manos no se mueven'
    assert abs(feet_low(J) - BH) < 3e-3, 'las rodillas deben apoyar en el suelo / banco'
    assert abs(J['near_leg'][1][0] - JA['near_leg'][1][0]) < 4e-3, 'las rodillas no se mueven'
    assert J['near_arm'][1][0] < J['S'][0] + 1e-6, 'codos hacia atras'
print('OK: arriba, abajo y a medio camino coinciden con los umbrales del contador (kneedeclinepushup)')
