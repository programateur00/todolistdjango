"""Flexiones con palmada (clap push-up), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones / flexiones-a-una-mano. SIN cara (ni nariz ni ojo ni oreja: cabeza lisa).
Como lo mira la app (workout.js: processClapPushup, CLAP_PUSHUP_*, counter "clappushup"): de PERFIL, boca abajo, como processPushup, pero la
repeticion SOLO cuenta si las manos DESPEGAN del suelo:
  - ARRIBA: codo >= PUSHUP_UP_ANGLE_DEG = 160 (para armar basta 145), cuerpo recto (hombro-cadera-tobillo >= PUSHUP_LINE_MIN_DEG = 150) y
    tumbado de verdad (inclinacion hombro-cadera <= ON_GROUND_MAX_TILT_DEG = 40); se guarda la altura de la muñeca apoyada (clapBaseY),
  - ABAJO: codo <= PUSHUP_COUNT_DOWN_ANGLE_DEG = 100 (el dibujo llega a <= 90),
  - EN EL AIRE (la palmada): las manos suben sobre clapBaseY entre CLAP_PUSHUP_MIN_LIFT_FACTOR = 0.09 y CLAP_PUSHUP_AIR_MAX_LIFT_FACTOR = 0.70 troncos,
    los HOMBROS suben por encima de su altura de arriba entre 0.05 y 0.45 troncos, codo >= CLAP_PUSHUP_MIN_AIR_ELBOW_DEG = 90,
    cuerpo recto (>= CLAP_PUSHUP_AIR_LINE_MIN_DEG = 120) y tronco como mucho a CLAP_PUSHUP_AIR_MAX_TILT_DEG = 52 (si no, es levantarse, no una palmada),
  - al caer vuelven las manos al suelo y los brazos se estiran: otra vez ARRIBA.
Los pies (puntas) NO se mueven: el cuerpo entero (recto como una tabla) gira alrededor de las puntas de los pies; las manos solo se mueven en el vuelo.
GIF de 4 fotogramas: arriba -> bajando (flecha gris abajo) -> abajo -> en el aire dando la palmada (flecha gris arriba y rayitas de impacto).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_flexiones_palmada.py [carpeta_salida] [clave=valor ...]   (genera flexiones-con-palmada.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbM=118, elbB=64, hand_dx=0.0, far_dx=-0.07, foot=292, footF=296, far_t=1.5, headd=9, margin=0.32,
           arrows=1, arrow_dx=1.05, arrow_len=0.42, fingers=1, toe_x=0.0,
           air_lift=0.50, air_rise=0.15, air_elb=110, air_far=0.05, burst=1, burst_len=0.24, hand_a=30)
# elbA/elbM/elbB: angulo del codo (grados) arriba / a medio camino / abajo (la app: >=160 arriba, <=90 abajo; cuenta con <=100 y >=130)
# hand_dx: x de las manos respecto al hombro de ARRIBA (0 = justo debajo del hombro; <0 = algo por detras); far_dx: la mano lejana queda algo detras
# foot / footF: angulo del pie cercano / lejano (apoyo en las puntas: ~290 = punta hacia abajo); far_t: grados que la pierna lejana se separa de la cercana
# headd: grados que la cabeza mira por encima de la linea del cuerpo (cuello neutro, mirada al suelo un poco por delante)
# air_lift: altura de las manos sobre el suelo EN EL AIRE, en troncos (la app: 0.09 - 0.70; en el log real de Alex las palmadas llegaban a <= 0.55)
# air_rise: cuanto suben los HOMBROS por encima de su altura de arriba, en troncos (la app: 0.05 - 0.45; log real <= 0.15)
# air_elb: angulo del codo en el aire (la app: >= 90; las manos se juntan por delante del pecho, brazos medio extendidos)
# air_far: cuanto queda la mano lejana por detras de la cercana en la palmada (para que se vean las dos); hand_a: giro extra de las manos en el aire (grados)
# burst / burst_len: rayitas de impacto de la palmada (1/0) y su largo; arrow_dx / arrow_len: posicion (delante de la cabeza) y largo de la flecha gris
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
CLAP_PUSHUP_MIN_LIFT_FACTOR = 0.09
CLAP_PUSHUP_MIN_AIR_ELBOW_DEG = 90
CLAP_PUSHUP_MIN_SHOULDER_RISE_FACTOR = 0.05
CLAP_PUSHUP_AIR_LINE_MIN_DEG = 120
CLAP_PUSHUP_AIR_MAX_LIFT_FACTOR = 0.70
CLAP_PUSHUP_AIR_MAX_SHOULDER_RISE = 0.45
CLAP_PUSHUP_AIR_MAX_TILT_DEG = 52

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
HX = _S[iA][0][0] + CFG['hand_dx']             # x de las manos (FIJAS mientras estan en el suelo)
HXF = HX + CFG['far_dx']                       # mano lejana, un pelin detras


def solve_elbow(elb):
    """t y cadera para que el codo (hombro-codo-muñeca) mida 'elb' grados con las manos en (HX, WY) y los pies fijos"""
    d = elbow_len(elb)
    cand = [i for i in range(len(_T)) if WY + 0.2 < _S[i][0][1] <= shA + 1e-6]
    i = min(cand, key=lambda i: abs(np.hypot(_S[i][0][0] - HX, _S[i][0][1] - WY) - d))
    assert abs(np.hypot(_S[i][0][0] - HX, _S[i][0][1] - WY) - d) < 4e-3, 'no hay solucion de postura para el codo %s' % elb
    return float(_T[i]), _S[i][1]


def solve_air():
    """EN EL AIRE: hombros 'air_rise' troncos por encima de su altura de arriba; manos juntas (palmada) 'air_lift' troncos sobre el suelo,
    por delante del pecho, con el codo en 'air_elb' grados. Los pies siguen apoyados en las puntas. Devuelve t, cadera, muñeca de la palmada."""
    ys = shA + CFG['air_rise']
    i = min(range(len(_T)), key=lambda i: abs(_S[i][0][1] - ys))
    assert abs(_S[i][0][1] - ys) < 2e-3, 'no hay solucion de postura en el aire'
    S_ = _S[i][0]
    wy = WY + CFG['air_lift']
    d = elbow_len(CFG['air_elb'])
    dy = S_[1] - wy
    assert d > dy, 'air_elb demasiado cerrado para esa altura de manos (el brazo no llega)'
    wx = S_[0] + float(np.sqrt(d * d - dy * dy))     # la palmada queda POR DELANTE del hombro
    return float(_T[i]), _S[i][1], (wx, wy)


tM, hipM = solve_elbow(CFG['elbM'])
tB, hipB = solve_elbow(CFG['elbB'])
tC, hipC, WC = solve_air()


def pose_aire(t, hip):
    p = pose_t(t, hip)
    H_ = np.array(hip, float); S_ = H_ + dv(t)
    wn = np.array(WC); wf = wn + np.array([-CFG['air_far'], 0.0])
    en, _ = ik2(S_, wn, L_UA, L_FA, 'cw'); ef, _ = ik2(S_, wf, L_UA, L_FA, 'cw')
    p['near_arm'] = ('ik', tuple(wn), 'cw'); p['far_arm'] = ('ik', tuple(wf), 'cw')
    p['near_hand'] = ang(wn - en) + CFG['hand_a']; p['far_hand'] = ang(wf - ef) + CFG['hand_a']
    return p


A, M, B, C = pose(tA, hipA), pose(tM, hipM), pose(tB, hipB), pose_aire(tC, hipC)

for p_ in (A, M, B, C):
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


def impacto(J):
    """rayitas de impacto de la palmada (grises, como las flechas) alrededor del punto donde chocan las manos"""
    def f(pen):
        if not CFG['burst']:
            return
        tip = J['near_handtip'] + np.array([0.03, 0.0])
        for a_ in (20, 62, 104):
            u = dv(a_)
            pen.line([tip + u * 0.09, tip + u * (0.09 + CFG['burst_len'])], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return f


def flecha(bajando, y0, y1, x):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (y0 + y1) / 2; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (x, a), (x, b))
    return f


JA, JM, JB, JC = build_side(A), build_side(M), build_side(B), build_side(C)
ax = JA['hd'][0] + CFG['arrow_dx']
# encuadre fijo para los 4 fotogramas (flecha y rayitas incluidas); el fotograma del aire es el mas alto
bb = (ax - 0.15, 0.0, ax + 0.15, JC['hd'][1] + 0.45)
frames = [A, M, B, C]
# la flecha de subida va a la altura de la subida: del suelo (hombro abajo) al hombro en el aire
extras = [[dedos(JA)],
          [dedos(JM), flecha(True, JB['S'][1], JA['S'][1], ax)],
          [dedos(JB)],
          [impacto(JC), flecha(False, JB['S'][1], JC['S'][1], ax)]]
imgs = render_scene(frames, OUT + 'flexiones-con-palmada', durations=[1200, 700, 1000, 1300], margin=CFG['margin'], bbox_extra=bb, extras=extras)


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


def tronco(J):
    return float(np.linalg.norm(J['S'] - J['H']))


def lift(J, sd):
    """(clapBaseY - muñeca.y) / tronco, con clapBaseY = altura de la muñeca apoyada arriba (y hacia arriba en el dibujo)"""
    return (J[sd + '_arm'][2][1] - JA['near_arm'][2][1]) / tronco(J)


def subida_hombro(J):
    """(clapShoulderBaseY - hombro.y) / tronco, con la altura del hombro ARRIBA como base"""
    return (J['S'][1] - JA['S'][1]) / tronco(JA)


for nombre, J in (('arriba', JA), ('a medio camino', JM), ('abajo', JB), ('en el aire', JC)):
    print(f"{nombre:15s}: codo {codo(J,'near'):.0f}° | linea hombro-cadera-tobillo {ang3(J['S'], J['H'], J['near_leg'][2]):.0f}° | "
          f"inclinacion {tilt(J):.0f}° | hombro a y={J['S'][1]:.2f} (sube {subida_hombro(J):+.2f} troncos) | "
          f"muñeca cercana ({J['near_arm'][2][0]:.2f}, {J['near_arm'][2][1]:.2f}) manos↑ {lift(J,'near'):.2f} / {lift(J,'far'):.2f} troncos")
assert codo(JA, 'near') >= PUSHUP_UP_ANGLE_DEG, 'arriba: el codo debe estar casi recto (>=160)'
assert codo(JB, 'near') <= PUSHUP_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar a <=90'
assert PUSHUP_COUNT_DOWN_ANGLE_DEG < codo(JM, 'near') < PUSHUP_UP_ANGLE_DEG, 'a medio camino: entre los dos umbrales'
for J in (JA, JM, JB):
    assert abs(lift(J, 'near')) < 3e-3 and abs(lift(J, 'far')) < 3e-3, 'en el suelo las manos estan apoyadas (levantar = 0)'
    assert np.allclose(J['near_arm'][2], JA['near_arm'][2], atol=3e-3), 'las manos no se mueven mientras estan en el suelo'
for J in (JA, JM, JB, JC):
    assert ang3(J['S'], J['H'], J['near_leg'][2]) >= PUSHUP_LINE_MIN_DEG, 'el cuerpo debe quedar en linea recta (hombro-cadera-tobillo >= 150)'
    assert tilt(J) <= ON_GROUND_MAX_TILT_DEG, 'tumbado de verdad: inclinacion hombro-cadera <= 40'
    assert tilt(J) < PUSHUP_BROKEN_TILT_DEG
    assert abs(feet_low(J)) < 3e-3, 'los pies deben tocar el suelo'
    assert abs(J['near_leg'][4][0] - JA['near_leg'][4][0]) < 2e-3, 'los pies no se mueven'
# --- el vuelo (airCand de processClapPushup)
for sd in ('near', 'far'):
    assert CLAP_PUSHUP_MIN_LIFT_FACTOR <= lift(JC, sd) <= CLAP_PUSHUP_AIR_MAX_LIFT_FACTOR, 'palmada: manos despegadas entre 0.09 y 0.70 troncos'
    assert codo(JC, sd) >= CLAP_PUSHUP_MIN_AIR_ELBOW_DEG, 'en el aire el codo >= 90'
assert CLAP_PUSHUP_MIN_SHOULDER_RISE_FACTOR <= subida_hombro(JC) <= CLAP_PUSHUP_AIR_MAX_SHOULDER_RISE, 'palmada: hombros 0.05 - 0.45 troncos por encima de su altura de arriba'
assert ang3(JC['S'], JC['H'], JC['near_leg'][2]) >= CLAP_PUSHUP_AIR_LINE_MIN_DEG
assert tilt(JC) <= CLAP_PUSHUP_AIR_MAX_TILT_DEG, 'en el aire el tronco no pasa de 52° (si no, es levantarse)'
assert JC['near_arm'][2][0] > JC['S'][0], 'la palmada queda por delante del hombro'
print('OK: arriba, abajo, a medio camino y en el aire coinciden con los umbrales del contador (clappushup)')
