"""Flexiones a una mano (one-arm push-up), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones / flexiones-inclinadas. SIN cara (ni nariz ni ojo ni oreja).
Como lo mira la app (workout.js: processOneArmPushup, ONEARM_PUSHUP_*, counter "onearmpushup", slug one-arm-push-up): de PERFIL, boca abajo, con
UN solo brazo apoyado (la muñeca MAS BAJA de la imagen) y la OTRA MANO LIBRE EN ALTO, detras de la espalda, a la vista:
  - para ARMAR: mano libre claramente por encima de la apoyada (>= ONEARM_PUSHUP_FREE_HAND_LIFT_FACTOR = 0.25 torsos; ya armado basta 0.10),
    codo apoyado casi recto (>= PUSHUP_ARM_GATE_ANGLE_DEG = 145), cuerpo recto (hombro-cadera-tobillo >= ONEARM_PUSHUP_LINE_MIN_DEG = 140)
    y tumbado de verdad (inclinacion hombro-cadera <= ON_GROUND_MAX_TILT_DEG = 40),
  - ARRIBA: codo apoyado >= PUSHUP_UP_ANGLE_DEG = 160; ABAJO: <= PUSHUP_DOWN_ANGLE_DEG = 90 (cuenta con <= 100); cuenta al volver a >= 130,
  - la mano apoyada y los pies NO se mueven: gira el cuerpo entero (recto como una tabla) alrededor de las puntas de los pies; la mano libre
    va pegada a la espalda y se mueve con el cuerpo (si la apoyas o te levantas, la serie se cierra).
GIF de 4 fotogramas: arriba -> bajando (flecha gris abajo) -> abajo -> subiendo (flecha gris arriba).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_flexiones_una_mano.py [carpeta_salida] [clave=valor ...]   (genera flexiones-a-una-mano.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbM=118, elbB=64, hand_dx=0.0, far_dx=-0.07, foot=292, footF=296, far_t=1.5, headd=9, margin=0.32,
           arrows=1, arrow_dx=1.05, arrow_len=0.42, fingers=1, toe_x=0.0,
           back_s=0.95, back_off=0.20, fbend=1, free_front=1, hand_a=0)
# elbA/elbM/elbB: angulo del codo (grados) arriba / a medio camino / abajo (la app: >=160 arriba, <=90 abajo; cuenta con <=100 y >=130)
# hand_dx: x de las manos respecto al hombro de ARRIBA (0 = justo debajo del hombro; <0 = algo por detras); far_dx: la mano lejana queda algo detras
# foot / footF: angulo del pie cercano / lejano (apoyo en las puntas: ~290 = punta hacia abajo); far_t: grados que la pierna lejana se separa de la cercana
# headd: grados que la cabeza mira por encima de la linea del cuerpo (cuello neutro, mirada al suelo un poco por delante)
# back_s / back_off: donde apoya la mano LIBRE en la espalda (fraccion del tronco desde el hombro hacia la cadera / separacion de la espalda en torsos); fbend: 0|1 hacia que lado se dobla el codo libre
# free_front: 1 = antebrazo y mano libres pintados encima de la espalda (se ven); hand_a: grados que se gira la mano libre respecto al antebrazo
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
ONEARM_PUSHUP_LINE_MIN_DEG = 140
ONEARM_PUSHUP_FREE_HAND_LIFT_FACTOR = 0.25
ONEARM_PUSHUP_FREE_HAND_LIFT_LOOSE_FACTOR = 0.10

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
    H_ = np.array(hip, float); S_ = H_ + dv(t)
    tgt = S_ + (H_ - S_) * CFG['back_s'] + dv(t + 90) * CFG['back_off']      # mano libre apoyada en la espalda (sigue al cuerpo)
    e_, w_ = ik2(S_, tgt, L_UA, L_FA, 'cw' if CFG['fbend'] else 'ccw')
    p['near_arm'] = ('ik', (HX, WY), bend); p['far_arm'] = ('ik', tuple(tgt), 'cw' if CFG['fbend'] else 'ccw')
    p['near_hand'] = HAND; p['far_hand'] = ang(w_ - e_) + CFG['hand_a']
    return p


# ARRIBA: el hombro a la altura que da el codo casi recto
iA = min(range(len(_T)), key=lambda i: abs(_S[i][0][1] - shA))
assert abs(_S[iA][0][1] - shA) < 2e-3, 'no hay solucion de postura arriba'
tA, hipA = float(_T[iA]), _S[iA][1]
HX = _S[iA][0][0] + CFG['hand_dx']             # x de las manos (FIJAS)


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


def mano_libre(J):
    """antebrazo y mano libres apoyados sobre la zona lumbar: se pintan DESPUES del cuerpo (por encima de la espalda); el codo asoma por detras"""
    def f(pen):
        sh, e_, w_ = J['far_arm']; tip = J['far_handtip']
        pen.paint(tube(e_, w_, 0.095, 0.085, bulge=0.13, peak=0.3) + tube(w_, tip, 0.085, 0.06, bulge=0.1, peak=0.4))
        u_ = (w_ - e_) / (np.linalg.norm(w_ - e_) + 1e-9); n_ = np.array([-u_[1], u_[0]])
        pen.line(smooth_curve([e_ + (w_ - e_) * 0.12 + n_ * 0.035, e_ + (w_ - e_) * 0.42 + n_ * 0.045, e_ + (w_ - e_) * 0.78 + n_ * 0.02]))
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
ex = lambda J, extra: [dedos(J)] + ([mano_libre(J)] if CFG['free_front'] else []) + extra
# encuadre fijo para los 4 fotogramas (flecha incluida)
bb = (ax - 0.15, 0.0, ax + 0.15, JA['hd'][1] + 0.4)
imgs = render_scene([A, M, B, M], OUT + 'flexiones-a-una-mano', durations=[1200, 700, 1300, 700], margin=CFG['margin'], bbox_extra=bb,
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
          f"muñeca ({J['near_arm'][2][0]:.2f}, {J['near_arm'][2][1]:.2f}) | mano libre en alto {(J['far_arm'][2][1]-J['near_arm'][2][1])/np.linalg.norm(J['S']-J['H']):.2f} torsos")
assert codo(JA, 'near') >= PUSHUP_UP_ANGLE_DEG, 'arriba: el codo debe estar casi recto (>=160)'
assert codo(JB, 'near') <= PUSHUP_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar a <=90'
assert PUSHUP_COUNT_DOWN_ANGLE_DEG < codo(JM, 'near') < PUSHUP_UP_ANGLE_DEG, 'a medio camino: entre los dos umbrales'
for J in (JA, JM, JB):
    assert ang3(J['S'], J['H'], J['near_leg'][2]) >= ONEARM_PUSHUP_LINE_MIN_DEG, 'el cuerpo debe quedar en linea recta (hombro-cadera-tobillo >= 140)'
    assert tilt(J) <= ON_GROUND_MAX_TILT_DEG, 'tumbado de verdad: inclinacion hombro-cadera <= 40'
    assert tilt(J) < PUSHUP_BROKEN_TILT_DEG
    lift = (J['far_arm'][2][1] - J['near_arm'][2][1]) / np.linalg.norm(J['S'] - J['H'])
    assert lift >= ONEARM_PUSHUP_FREE_HAND_LIFT_FACTOR, 'la mano libre debe quedar claramente por encima de la apoyada (>= 0.25 torsos)'
    assert J['far_arm'][2][1] > J['near_arm'][2][1] and J['near_arm'][2][1] < min(J['far_arm'][1][1], J['far_arm'][2][1]), 'la muñeca apoyada debe ser la mas baja'
    assert np.allclose(J['near_arm'][2], JA['near_arm'][2], atol=1e-6), 'las manos no se mueven'
    assert abs(feet_low(J)) < 3e-3, 'los pies deben tocar el suelo'
    assert J['near_leg'][4][0] == JA['near_leg'][4][0] or abs(J['near_leg'][4][0] - JA['near_leg'][4][0]) < 2e-3, 'los pies no se mueven'
print('OK: arriba, abajo y a medio camino coinciden con los umbrales del contador (onearmpushup)')
