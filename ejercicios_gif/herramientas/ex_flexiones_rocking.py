"""Rocking push-ups, vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones / pseudo planche. SIN cara (ni nariz ni ojo ni oreja: no se usa cara()).
Como lo mira la app (workout.js: processRockingPushup, counter "rockingpushup", slug rocking-push-up, migracion 0115): de PERFIL, armado en
PLANCHA ALTA (brazos estirados, cuerpo recto). Cada repeticion son DOS cosas (da igual el orden):
  - FLEXION: el codo baja hasta <= PUSHUP_COUNT_DOWN_ANGLE_DEG = 100 (en el GIF 64°) y vuelve a >= PUSHUP_COUNT_UP_ANGLE_DEG = 130, solo con el cuerpo en
    plancha (angulo hombro-cadera-RODILLA >= ROCKPUSHUP_PLANK_MIN_DEG = 140 e inclinacion hombro-cadera <= ROCKPUSHUP_COUNT_MAX_TILT_DEG = 45),
  - BALANCEO: con los BRAZOS ESTIRADOS la cadera se va HACIA ATRAS, hacia los talones (postura del niño): el angulo hombro-cadera-rodilla se cierra hasta
    <= ROCKPUSHUP_ROCK_BACK_DEG = 110 y luego vuelve a >= ROCKPUSHUP_ROCK_RETURN_DEG = 150 (de vuelta en plancha),
  - manos y pies NO se mueven del sitio donde se armo (mano/tobillo a menos de 0.6 largos de tronco); la serie se cierra si el tronco pasa de 65° de inclinacion.
GIF de 8 fotogramas: plancha -> bajando (flecha gris abajo) -> abajo -> subiendo (flecha gris arriba) -> plancha -> cadera atras (flecha gris hacia atras)
-> cadera sobre los talones -> volviendo (flecha gris hacia delante) -> (vuelta a la plancha).
La geometria se RESUELVE (no se dibuja a ojo): manos y puntas de los pies fijas; en el balanceo el hombro sale de cortar "tronco = 1" con "brazo estirado"
y la rodilla de la IK de la pierna con el tobillo fijo (rodillas al suelo, sentado sobre los talones con las puntas apoyadas).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_flexiones_rocking.py [carpeta_salida] [clave=valor ...]   (genera rocking-push-ups.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbM=118, elbB=64, hand_dx=0.0, far_dx=-0.07, foot=292, footF=296, far_t=1.5, headd=9, headR=20, margin=0.32,
           arrows=1, arrow_dx=1.05, arrow_len=0.42, harrow_len=0.62, harrow_y=0.45, fingers=1, toe_x=0.0,
           rock_dx=0.90, rock_mid=0.5, knee_gap=0.0, durA=1000, durB=1000, durR=1300, durM=600)
# elbA/elbM/elbB: angulo del codo (grados) arriba / a medio camino / abajo de la flexion (la app: >=160 arriba, cuenta con <=100 y >=130)
# hand_dx: x de las manos respecto al hombro de ARRIBA (0 = justo debajo del hombro); far_dx: la mano lejana queda algo detras
# foot / footF: angulo del pie cercano / lejano (apoyo en las puntas: ~290 = punta hacia abajo); far_t: grados que la pierna lejana se separa de la cercana
# headd / headR: grados que la cabeza mira por encima de la linea del cuerpo en la plancha / en el balanceo (headR<0 = mirando al suelo)
# rock_dx: x de la cadera respecto al tobillo cuando se sienta sobre los talones (>0 = algo por delante de los tobillos); rock_mid: fraccion del balanceo del fotograma intermedio;
# knee_gap: cuanto queda la rodilla por encima del suelo (0 = apoyada); harrow_len / harrow_y: largo y altura (sobre el hombro de la plancha) de la flecha horizontal del balanceo
# arrow_dx / arrow_len: posicion (delante de la cabeza) y largo de la flecha gris vertical de la flexion
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
PUSHUP_UP_ANGLE_DEG = 160
PUSHUP_COUNT_DOWN_ANGLE_DEG = 100
PUSHUP_COUNT_UP_ANGLE_DEG = 130
PUSHUP_ARM_GATE_ANGLE_DEG = 145
ON_GROUND_MAX_TILT_DEG = 40
ROCKPUSHUP_LINE_MIN_DEG = 150
ROCKPUSHUP_PLANK_MIN_DEG = 140
ROCKPUSHUP_ROCK_BACK_DEG = 110
ROCKPUSHUP_ROCK_RETURN_DEG = 150
ROCKPUSHUP_BROKEN_TILT_DEG = 65
ROCKPUSHUP_COUNT_MAX_TILT_DEG = 45
ROCKPUSHUP_HAND_MOVE_FACTOR = 0.6
ROCKPUSHUP_FOOT_MOVE_FACTOR = 0.6

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


# ---- la flexion: el cuerpo gira como una tabla alrededor de las puntas de los pies (que NO se mueven) ----
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


iA = min(range(len(_T)), key=lambda i: abs(_S[i][0][1] - shA))
assert abs(_S[iA][0][1] - shA) < 2e-3, 'no hay solucion de postura arriba'
tA, hipA = float(_T[iA]), _S[iA][1]
HX = _S[iA][0][0] + CFG['hand_dx']             # x de las manos (FIJAS)
HXF = HX + CFG['far_dx']                       # mano lejana, un pelin detras
W = np.array([HX, WY])


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
JA, JM, JB = build_side(A), build_side(M), build_side(B)
for J_ in (JA, JM, JB):
    assert J_['near_arm'][1][0] < J_['S'][0] + 1e-6, 'el codo debe quedar detras del hombro (codos hacia atras), cambia ccw/cw'

# ---- el balanceo: manos y puntas de los pies FIJAS; la cadera va hacia atras y baja hasta sentarse sobre los talones ----
ANN, ANF = JA['near_leg'][2].copy(), JA['far_leg'][2].copy()        # tobillos de la plancha (no se mueven)
LEG = L_THIGH + L_SHIN


def knees(H):
    kn, _ = ik2(H, ANN, L_THIGH, L_SHIN, 'ccw'); kf, _ = ik2(H, ANF, L_THIGH, L_SHIN, 'ccw')
    return kn, kf


def hip_y_for(hx):
    """la cadera mas baja con esa x en la que las rodillas no atraviesan el suelo (con el mismo margen que figura.ground_shift)"""
    for hy in np.arange(0.25, 2.4, 0.001):
        H = np.array([hx, hy])
        if max(np.linalg.norm(H - ANN), np.linalg.norm(H - ANF)) >= LEG - 0.02:
            continue
        if min(k[1] for k in knees(H)) - 0.13 >= CFG['knee_gap']:
            return float(hy)
    raise AssertionError('no hay postura de balanceo con rock_dx=%s' % CFG['rock_dx'])


def shoulder_for(H):
    """hombro: a 1 (tronco) de la cadera y a 'brazo estirado' de la muñeca; de las dos soluciones, la de arriba"""
    v = W - H; D = float(np.linalg.norm(v)); u = v / D
    a_ = (1.0 - dA * dA + D * D) / (2 * D); h2 = 1.0 - a_ * a_
    assert h2 >= 0, 'con esa cadera el brazo no llega a la mano'
    perp = np.array([-u[1], u[0]]); h = np.sqrt(h2)
    return max((H + u * a_ + perp * h, H + u * a_ - perp * h), key=lambda p_: p_[1])


def rock_pose(s):
    """s = 0 plancha, 1 sentado sobre los talones. Cadera: x interpolada, y la mas baja sin hundir las rodillas en el suelo"""
    hx = hipA[0] + s * ((ANN[0] + CFG['rock_dx']) - hipA[0])
    H = np.array([hx, hip_y_for(hx)])
    S = shoulder_for(H); t = ang(S - H)
    p = dict(f=1, ground=False, hip=tuple(H), torso=t, head=t + CFG['headd'] * (1 - s) + CFG['headR'] * s,
             near_leg=('ik', tuple(ANN), 'ccw', CFG['foot']), far_leg=('ik', tuple(ANF), 'ccw', CFG['footF']),
             near_arm=('ik', (HX, WY), 'cw'), far_arm=('ik', (HXF, WY), 'cw'), near_hand=HAND, far_hand=HAND)
    return p


RM, R = rock_pose(CFG['rock_mid']), rock_pose(1.0)
JRM, JR = build_side(RM), build_side(R)


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


def flecha_h(atras, xc, y):
    def f(pen):
        if not CFG['arrows']:
            return
        h = CFG['harrow_len'] / 2
        a, b = (xc + h, xc - h) if atras else (xc - h, xc + h)
        draw_line_arrow(pen, (a, y), (b, y))
    return f


ax = JA['hd'][0] + CFG['arrow_dx']                 # flecha vertical de la flexion, delante de la cabeza
hx_c = (hipA[0] + ANN[0] + CFG['rock_dx']) / 2     # flecha horizontal del balanceo, sobre la cadera
hy_a = JA['S'][1] + CFG['harrow_y']
ex = lambda J, extra: [dedos(J)] + extra
# encuadre fijo para los 8 fotogramas (flechas incluidas)
bb = (min(ax - 0.15, hx_c - CFG['harrow_len'] / 2 - 0.1), 0.0, ax + 0.15, max(JA['hd'][1] + 0.4, hy_a + 0.15))
frames = [A, M, B, M, A, RM, R, RM]
durs = [CFG['durA'], CFG['durM'], CFG['durB'], CFG['durM'], CFG['durA'] - 200, CFG['durM'], CFG['durR'], CFG['durM']]
imgs = render_scene(frames, OUT + 'rocking-push-ups', durations=durs, margin=CFG['margin'], bbox_extra=bb,
                    extras=[ex(JA, []), ex(JM, [flecha(True, JB['S'][1], JA['S'][1], ax)]), ex(JB, []),
                            ex(JM, [flecha(False, JB['S'][1], JA['S'][1], ax)]), ex(JA, []),
                            ex(JRM, [flecha_h(True, hx_c, hy_a)]), ex(JR, []), ex(JRM, [flecha_h(False, hx_c, hy_a)])])


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


def cadera(J):
    """el angulo que mide el contador: hombro-cadera-RODILLA"""
    return ang3(J['S'], J['H'], J['near_leg'][1])


NOMBRES = (('plancha', JA), ('flexion a medio camino', JM), ('flexion abajo', JB), ('balanceo a medio camino', JRM), ('sentado en los talones', JR))
for nombre, J in NOMBRES:
    print(f"{nombre:24s}: codo {codo(J,'near'):.0f}° | hombro-cadera-rodilla {cadera(J):.0f}° | inclinacion {tilt(J):.0f}° | "
          f"cadera ({J['H'][0]:.2f}, {J['H'][1]:.2f}) | rodilla y={J['near_leg'][1][1]:.2f} | hombro y={J['S'][1]:.2f} | cabeza y={J['hd'][1]:.2f}")
# plancha alta (armar)
assert codo(JA, 'near') >= PUSHUP_UP_ANGLE_DEG and codo(JA, 'far') >= PUSHUP_UP_ANGLE_DEG, 'plancha: el codo debe estar casi recto (>=160)'
assert codo(JA, 'near') >= PUSHUP_ARM_GATE_ANGLE_DEG
assert cadera(JA) >= ROCKPUSHUP_LINE_MIN_DEG, 'plancha: hombro-cadera-rodilla >= 150 para armar'
assert tilt(JA) <= ON_GROUND_MAX_TILT_DEG, 'plancha: tumbado de verdad (inclinacion <= 40)'
# flexion
assert codo(JB, 'near') <= PUSHUP_COUNT_DOWN_ANGLE_DEG and codo(JB, 'far') <= PUSHUP_COUNT_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar a <=100 (cuenta)'
assert PUSHUP_COUNT_DOWN_ANGLE_DEG < codo(JM, 'near') < PUSHUP_UP_ANGLE_DEG, 'a medio camino de la flexion: entre los dos umbrales'
for J in (JA, JM, JB):
    assert cadera(J) >= ROCKPUSHUP_PLANK_MIN_DEG, 'la flexion solo cuenta con el cuerpo en plancha (hombro-cadera-rodilla >= 140)'
    assert tilt(J) <= ROCKPUSHUP_COUNT_MAX_TILT_DEG, 'la flexion solo cuenta con inclinacion <= 45'
# balanceo: brazos estirados, cadera atras
assert codo(JR, 'near') >= PUSHUP_COUNT_UP_ANGLE_DEG and codo(JR, 'far') >= PUSHUP_COUNT_UP_ANGLE_DEG, 'balanceo: los brazos siguen estirados (>=130)'
assert codo(JRM, 'near') >= PUSHUP_COUNT_UP_ANGLE_DEG
assert cadera(JR) <= ROCKPUSHUP_ROCK_BACK_DEG - 10, 'sentado en los talones: hombro-cadera-rodilla <= 110 (con margen)'
assert ROCKPUSHUP_ROCK_BACK_DEG < cadera(JRM) < ROCKPUSHUP_ROCK_RETURN_DEG + 25, 'balanceo a medio camino: cadera a medio cerrar'
for J in (JR, JRM):
    assert tilt(J) < ROCKPUSHUP_BROKEN_TILT_DEG, 'el tronco no debe pasar de 65° (se daria la serie por terminada)'
# apoyos fijos y suelo
for J in (JA, JM, JB, JRM, JR):
    sc = float(np.linalg.norm(J['S'] - J['H']))
    assert np.linalg.norm(J['near_arm'][2] - JA['near_arm'][2]) <= 1e-6 + 0.0 * ROCKPUSHUP_HAND_MOVE_FACTOR * sc, 'las manos no se mueven'
    assert np.linalg.norm(J['near_leg'][2] - JA['near_leg'][2]) <= 0.01, 'los pies (tobillos) no se mueven'
    assert abs(J['near_leg'][4][0] - JA['near_leg'][4][0]) < 0.01, 'las puntas de los pies no se mueven'
for J in (JA, JM, JB):
    assert abs(feet_low(J)) < 3e-3, 'los pies deben tocar el suelo'
for nombre, J in (('balanceo a medio camino', JRM), ('sentado en los talones', JR)):
    low = feet_low(J)
    assert low >= -0.01, f'{nombre}: las piernas no deben atravesar el suelo (punto mas bajo {low:.3f})'
    assert J['H'][1] - 0.20 >= -0.01 and J['hd'][1] - 0.27 >= -0.01 and J['S'][1] - 0.15 >= -0.01, f'{nombre}: cadera, cabeza y hombro por encima del suelo'
print('OK: plancha, flexion y balanceo coinciden con los umbrales del contador (rockingpushup)')
