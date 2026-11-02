"""Flexiones en pino (handstand push-ups), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que pike-push-ups / flexiones. SIN cara (ni nariz ni ojo ni oreja).
Como lo mira la app (workout.js: processHandstandPushup, counter "handstandpushup", slug handstand-push-up; la postura es la de
checkHandstandPosture, valen vista de frente o de lado): en el PINO, boca abajo con las manos en el suelo y una rep = bajar la cabeza hacia
el suelo doblando los codos y volver a estirarlos:
  - POSTURA en todos los fotogramas: cadera POR ENCIMA de los hombros (margen HANDSTAND_MARGIN_FACTOR = 0.08 anchos de hombro), codos y
    muñecas por DEBAJO de la cadera, muñecas por debajo de los hombros, y los tobillos (y rodillas) por encima de la cadera
    (HANDSTAND_ANKLE_ABOVE_HIP_FACTOR = 0.6, HANDSTAND_KNEE_ABOVE_HIP_FACTOR = 0.3 anchos de hombro),
  - ARRIBA = brazos estirados (codo >= HANDSTANDPUSHUP_ARM_GATE_DEG = 140 para armar), cuerpo recto, cabeza entre los brazos,
  - ABAJO: el codo se dobla hasta <= HANDSTANDPUSHUP_DOWN_ANGLE_DEG = 105 y la cabeza baja casi hasta el suelo, delante de las manos,
  - la repeticion cuenta al volver a estirar (>= HANDSTANDPUSHUP_UP_ANGLE_DEG = 125),
  - las manos NO se mueven; las puntas de los pies se apoyan en la pared (pino con la BARRIGA hacia la pared) y resbalan por ella al bajar.
GIF de 4 fotogramas: arriba -> bajando (flecha gris abajo) -> abajo -> subiendo (flecha gris arriba).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_flexiones_pino.py [carpeta_salida] [clave=valor ...]   (genera flexiones-en-pino.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbM=115, elbB=88, lean=0, tilt=6, head_gap=0.06, headd=0, headdB=10, far_dx=-0.07, far_tilt=0,
           foot=105, footF=105, wall=1, wall_gap=0.07, margin=0.12, arrows=1, arrow_dx=0.7, arrow_len=0.6, fingers=1)
# elbA/elbM/elbB: angulo del codo (grados) arriba / a medio camino / abajo (la app: >=140 arriba, <=105 abajo, cuenta al volver a >=125;
#   a medio camino se queda entre 105 y 125: ni arriba ni abajo); lean: grados que el brazo se inclina hacia atras ARRIBA (0 = hombro justo sobre la muñeca)
# tilt: inclinacion (grados) del cuerpo hacia la pared ARRIBA; abajo se calcula sola porque los pies siguen apoyados en la pared
# head_gap: hueco entre la cabeza y el suelo ABAJO (la cabeza casi toca); headd / headdB: grados que la cabeza gira respecto al tronco arriba / abajo
# far_dx: mano lejana, algo detras; far_tilt: grados que la pierna lejana va menos inclinada hacia la pared (0 = tapada por la cercana, limpio)
# foot / footF: angulo del pie cercano / lejano (105 = puntas estiradas hacia arriba y algo hacia la pared); wall=0 quita la pared (los pies quedan en el aire)
# wall_gap: separacion pared-puntas; arrow_dx / arrow_len: posicion (delante de la cabeza) y largo de la flecha gris
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
HANDSTAND_MARGIN_FACTOR = 0.08
HANDSTAND_ANKLE_ABOVE_HIP_FACTOR = 0.6
HANDSTAND_KNEE_ABOVE_HIP_FACTOR = 0.3
HANDSTANDPUSHUP_ARM_GATE_DEG = 140
HANDSTANDPUSHUP_DOWN_ANGLE_DEG = 105
HANDSTANDPUSHUP_UP_ANGLE_DEG = 125
SHOULDER_W = 0.68               # ancho de hombros del muñeco visto de frente (figura.build_front: 2 * 0.34), la unidad de los factores de arriba

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo
LEG = L_THIGH + L_SHIN          # pierna recta
BODY = 1.0 + LEG                # hombro -> tobillo con el cuerpo recto (torso 1 + pierna)
W = np.array([0.0, WY])         # muñeca cercana (FIJA)


def elbow_len(deg):
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


# ---- PIES: figura.py dibuja zapatillas planas (de pie); en el pino los pies van con las puntas estiradas hacia arriba, asi que se sustituyen
# por un pie en punta que sigue la linea de la pierna: tobillo estrecho, talon que sobresale por DETRAS (hacia fuera de la pared), empeine
# por delante (hacia la pared) y puntas redondeadas. Se parchean limb_leg (donde queda la puntera, para las rayitas de los dedos) y foot_poly.
_limb_leg = figura.limb_leg


def limb_leg_pino(spec, H):
    hp, k, a, he, to = _limb_leg(spec, H)
    d = dv(spec[3]); p = rot(d, -90)
    to = a + d * 0.40 - p * 0.03                         # puntera (dentro del pie: ahi dibuja figura las rayitas de los dedos)
    return hp, k, a, to - d * 0.44, to


# pie en el sistema (u a lo largo de las puntas, v hacia la planta/talon = detras), con el tobillo en (0, 0)
PIE_UV = np.array([(-0.03, -0.075), (0.07, -0.085), (0.20, -0.085), (0.33, -0.075), (0.44, -0.058), (0.52, -0.03), (0.545, 0.012),
                   (0.50, 0.052), (0.41, 0.075), (0.29, 0.090), (0.16, 0.112), (0.05, 0.140), (-0.04, 0.140), (-0.085, 0.105), (-0.06, 0.07)])


def foot_poly_pino(an, he, to):
    d = (to - he) / (np.linalg.norm(to - he) + 1e-9); p = rot(d, -90)
    return np.array([an + u * d + v * p for u, v in PIE_UV])


figura.limb_leg = limb_leg_pino
figura.foot_poly = foot_poly_pino
foot_poly = foot_poly_pino


def foot_left(foot):
    """x del punto mas a la izquierda del pie (hacia la pared) respecto al tobillo"""
    hp, k, a, he, to = limb_leg_pino(('fk', 90, 90, foot), np.zeros(2))
    return float(foot_poly(a, he, to)[:, 0].min() - a[0])


def line_state(S, tau):
    """cuerpo RECTO (hombro-cadera-tobillo en linea) inclinado tau grados hacia la pared (izquierda); la cadera esta a 1 torso por encima del hombro"""
    up = dv(90 + tau)
    return dict(S=S, H=S + up, A=S + BODY * up, tau=tau, leg=90 + tau, t=-90 + tau)


# ARRIBA: brazos estirados, hombro sobre la muñeca; el cuerpo recto se inclina `tilt` grados hacia la pared y las puntas de los pies la tocan
S_A = W + elbow_len(CFG['elbA']) * dv(90 + CFG['lean'])
A = line_state(S_A, CFG['tilt']); A.update(elb=CFG['elbA'], headd=CFG['headd'])
X_OFF = foot_left(CFG['foot'])                                     # punta del pie respecto al tobillo
X_WALL = A['A'][0] + X_OFF - CFG['wall_gap']                       # x de la pared
X_ANK = X_WALL + CFG['wall_gap'] - X_OFF                           # x que tiene que tener el tobillo para que las puntas toquen la pared


def at_shoulder(S, elb, headd):
    """estado con el hombro en S: con pared el angulo se calcula para que el tobillo quede en X_ANK; sin pared se mantiene tilt"""
    if CFG['wall']:
        s = (S[0] - X_ANK) / BODY
        if abs(s) >= 1:
            return None
        tau = float(np.rad2deg(np.arcsin(s)))
    else:
        tau = CFG['tilt']
    st = line_state(S, tau); st.update(elb=elb, headd=headd)
    return st


def shoulder_xy(elb, dx):
    """hombro a la distancia hombro-muñeca que da ese codo, dx por delante de la muñeca"""
    d = elbow_len(elb)
    if abs(dx) >= d:
        return None
    return W + np.array([dx, np.sqrt(d * d - dx * dx)])


def head_low(st):
    hd = st['S'] + dv(st['t'] + st['headd']) * NECK_HEAD
    return hd[1] - 0.27


# ABAJO: codo elbB y la cabeza casi tocando el suelo (el hombro avanza para que la cabeza baje delante de las manos)
cand = []
for dx in np.arange(0.0, elbow_len(CFG['elbB']) - 1e-3, 0.002):
    S_ = shoulder_xy(CFG['elbB'], dx)
    st = at_shoulder(S_, CFG['elbB'], CFG['headdB']) if S_ is not None else None
    if st is not None:
        cand.append((abs(head_low(st) - CFG['head_gap']), dx, st))
_best = min(cand, key=lambda c: c[0])
assert _best[0] < 1.5e-2, 'no hay postura abajo con la cabeza a head_gap del suelo (cambia elbB/head_gap/tilt)'
B = _best[2]
# A MEDIO CAMINO: el hombro a media altura entre arriba y abajo, con el codo elbM
dy_m = (A['S'][1] + B['S'][1]) / 2 - WY
d_m = elbow_len(CFG['elbM'])
assert abs(dy_m) < d_m, 'no hay solucion de postura a medio camino (cambia elbM)'
M = at_shoulder(W + np.array([np.sqrt(d_m * d_m - dy_m * dy_m), dy_m + 0]), CFG['elbM'], (A['headd'] + B['headd']) / 2)
assert M is not None


def elbow_back(S, e):
    """el codo queda detras (hacia la pared) de la recta hombro-muñeca a su altura"""
    xl = S[0] + (W[0] - S[0]) * (S[1] - e[1]) / (S[1] - W[1])
    return e[0] <= xl + 1e-6


def pose(st):
    p = dict(f=1, ground=False, hip=tuple(st['H']), torso=st['t'], head=st['t'] + st['headd'],
             near_leg=('fk', st['leg'], st['leg'], CFG['foot']), far_leg=('fk', st['leg'] - CFG['far_tilt'], st['leg'] - CFG['far_tilt'], CFG['footF']))
    HX, HXF = W[0], W[0] + CFG['far_dx']
    S = st['S']
    for bend in ('cw', 'ccw'):                           # los codos van HACIA ATRAS (hacia la pared, detras de la recta hombro-muñeca)
        e, _ = ik2(S, W, L_UA, L_FA, bend)
        if elbow_back(S, e):
            break
    p['near_arm'] = ('ik', (HX, WY), bend); p['far_arm'] = ('ik', (HXF, WY), bend)
    p['near_hand'] = HAND; p['far_hand'] = HAND
    return p


PA, PM, PB = pose(A), pose(M), pose(B)
JA, JM, JB = build_side(PA), build_side(PM), build_side(PB)


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


def pared(pen):
    """la pared: raya gris vertical del suelo hasta arriba del todo (mismo gris y grosor que el suelo)"""
    if not CFG['wall']:
        return
    x = pen.c.C((X_WALL, 0))[0]; fy = pen.c.C((0, -0.055))[1]
    cv2.line(pen.img, (int(round(x)), 0), (int(round(x)), int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)


_draw_side = figura.draw_side


def draw_side_con_pared(pen, J, props_back=None):
    pared(pen)                                           # la pared va DETRAS del muñeco (el muñeco se pinta con relleno blanco encima)
    _draw_side(pen, J, props_back)


figura.draw_side = draw_side_con_pared


def flecha(bajando, y0, y1, x):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (y0 + y1) / 2; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (x, a), (x, b))
    return f


ax = max(JA['hd'][0], JM['hd'][0], JB['hd'][0]) + CFG['arrow_dx']
ex = lambda J, extra: [dedos(J)] + extra
bb = (X_WALL - 0.1, -0.1, ax + 0.15, A['A'][1] + 0.62)
imgs = render_scene([PA, PM, PB, PM], OUT + 'flexiones-en-pino', ground_all=False,
                    durations=[1200, 700, 1300, 700], margin=CFG['margin'], bbox_extra=bb,
                    extras=[ex(JA, []), ex(JM, [flecha(True, JB['hd'][1], JA['hd'][1], ax)]), ex(JB, []),
                            ex(JM, [flecha(False, JB['hd'][1], JA['hd'][1], ax)])])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def codo(J, sd):
    sh, e, w_ = J[sd + '_arm']; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def foot_min_x(J):
    xs = []
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        xs.append(foot_poly(a, he, to)[:, 0].min())
    return min(xs)


MARGIN = HANDSTAND_MARGIN_FACTOR * SHOULDER_W
for nombre, J in (('arriba', JA), ('a medio camino', JM), ('abajo', JB)):
    hip, sh = J['H'], J['S']
    ankle, knee = J['near_leg'][2], J['near_leg'][1]
    wr, el = J['near_arm'][2], J['near_arm'][1]
    print(f"{nombre:15s}: codo {codo(J,'near'):.0f}° | cadera sobre hombro {hip[1]-sh[1]:.2f} (mín {MARGIN:.2f}) | tobillo sobre cadera {ankle[1]-hip[1]:.2f} "
          f"(mín {HANDSTAND_ANKLE_ABOVE_HIP_FACTOR*SHOULDER_W:.2f}) | codo bajo cadera {hip[1]-el[1]:.2f} muñeca bajo cadera {hip[1]-wr[1]:.2f} | "
          f"hombro-cadera-tobillo {ang3(sh, hip, ankle):.0f}° | rodilla {ang3(hip, knee, ankle):.0f}° | inclinación {J['H'][0]-J['S'][0]:+.2f} | "
          f"hombro ({sh[0]:.2f}, {sh[1]:.2f}) cabeza más baja y={J['hd'][1]-0.27:.2f} x={J['hd'][0]:.2f} | pie más a la izq. x={foot_min_x(J):.2f} (pared {X_WALL+CFG['wall_gap']:.2f})")
assert codo(JA, 'near') >= HANDSTANDPUSHUP_ARM_GATE_DEG and codo(JA, 'far') >= HANDSTANDPUSHUP_ARM_GATE_DEG, 'arriba: los brazos deben estar estirados (>=140)'
assert codo(JB, 'near') <= HANDSTANDPUSHUP_DOWN_ANGLE_DEG and codo(JB, 'far') <= HANDSTANDPUSHUP_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar a <=105'
assert HANDSTANDPUSHUP_DOWN_ANGLE_DEG < codo(JM, 'near') < HANDSTANDPUSHUP_UP_ANGLE_DEG, 'a medio camino: entre los dos umbrales (105-125), ni arriba ni abajo'
assert codo(JA, 'near') >= HANDSTANDPUSHUP_UP_ANGLE_DEG, 'arriba cuenta como rep completa (>=125)'
for J in (JA, JM, JB):
    hip, sh = J['H'], J['S']
    ankle, knee = J['near_leg'][2], J['near_leg'][1]
    kneeF, ankleF = J['far_leg'][1], J['far_leg'][2]
    # checkHandstandPosture / processHandstandPushup: invertida/o (Y menor en la imagen = mayor aqui) y brazos aguantando el peso cerca del suelo
    assert hip[1] > sh[1] + MARGIN, 'la cadera debe quedar por encima de los hombros (invertida/o)'
    for sd in ('near', 'far'):
        s_, e_, w_ = J[sd + '_arm']
        assert e_[1] < hip[1] - MARGIN and w_[1] < hip[1] - MARGIN, 'codos y muñecas por debajo de la cadera'
        assert w_[1] < sh[1] - MARGIN, 'muñecas por debajo de los hombros'
    assert ankle[1] > hip[1] + HANDSTAND_ANKLE_ABOVE_HIP_FACTOR * SHOULDER_W and ankleF[1] > hip[1] + HANDSTAND_ANKLE_ABOVE_HIP_FACTOR * SHOULDER_W, 'tobillos claramente por encima de la cadera'
    assert knee[1] > hip[1] + HANDSTAND_KNEE_ABOVE_HIP_FACTOR * SHOULDER_W, 'rodillas por encima de la cadera'
    assert ang3(hip, knee, ankle) > 178, 'piernas rectas'
    assert ang3(sh, hip, ankle) > 175, 'cuerpo recto (hombro-cadera-tobillo en linea)'
    assert elbow_back(J['S'], J['near_arm'][1]), 'el codo debe quedar detras de la recta hombro-muñeca (hacia la pared), cambia ccw/cw'
    assert np.allclose(J['near_arm'][2], JA['near_arm'][2], atol=1e-6), 'las manos no se mueven'
    assert J['hd'][1] - 0.27 > -0.01, 'la cabeza no puede atravesar el suelo'
    if CFG['wall']:
        for sd in ('near', 'far'):
            assert J[sd + '_arm'][1][0] > X_WALL + 0.15, 'los codos no atraviesan la pared (quedan delante de ella)'
        assert J['hd'][0] - 0.3 > X_WALL, 'la cabeza no atraviesa la pared'
    if CFG['wall']:
        assert abs(foot_min_x(J) - (X_WALL + CFG['wall_gap'])) < 1e-6 and J['H'][0] > X_WALL, 'las puntas de los pies tocan la pared'
assert JB['hd'][1] - 0.27 < 0.12, 'abajo la cabeza queda casi pegada al suelo'
assert JB['hd'][0] > JB['near_arm'][2][0], 'la cabeza baja DELANTE de las manos (hacia los dedos), no encima de ellas'
print('OK: arriba, abajo y a medio camino coinciden con los umbrales del contador (handstandpushup)')
