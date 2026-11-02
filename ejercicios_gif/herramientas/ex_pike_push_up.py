"""Pike push-ups (flexiones en V invertida), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones / flexiones-inclinadas / pseudo-planche. SIN cara (ni nariz ni ojo ni oreja).
Como lo mira la app (workout.js: processPikePushup, counter "pikepushup", slug pike-push-up): de PERFIL, en V invertida (manos y pies en el suelo,
brazos y piernas estirados, caderas en lo alto) y una rep = bajar la cabeza hacia el suelo doblando los brazos y volver a estirarlos:
  - POSTURA en todos los fotogramas: caderas claramente POR ENCIMA del hombro (>= PIKE_MIN_HIP_RISE_FACTOR = 0.25 torsos; ya armado basta 0.10),
    cuerpo doblado (hombro-cadera-tobillo <= PIKE_BODY_MAX_DEG = 145; ya armado <= 165) y manos/pies a la misma altura (|muñeca - tobillo| <= 1.0 torsos),
  - ARRIBA = brazos estirados (codo >= PIKE_ARM_GATE_DEG = 145 para armar), piernas rectas, cabeza colgando entre los brazos,
  - ABAJO: el codo se dobla hasta <= PIKE_DOWN_ANGLE_DEG = 115 y la cabeza baja casi hasta el suelo, delante de las manos,
  - la repeticion cuenta al volver a estirar (>= PIKE_UP_ANGLE_DEG = 145),
  - manos y pies NO se mueven (las caderas se adelantan y bajan un poco al bajar; las piernas siguen rectas).
GIF de 4 fotogramas: arriba -> bajando (flecha gris abajo) -> abajo -> subiendo (flecha gris arriba).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_pike_push_up.py [carpeta_salida] [clave=valor ...]   (genera pike-push-ups.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbM=130, elbB=88, foot_x=-1.5, lean=4, head_gap=0.07, headd=8, headdB=0, far_dx=-0.07, far_foot_dx=-0.07,
           foot=350, footF=350, margin=0.32, arrows=1, arrow_dx=0.62, arrow_len=0.5, fingers=1, legB=0)
# elbA/elbM/elbB: angulo del codo (grados) arriba / a medio camino / abajo (la app: >=145 arriba, <=115 abajo; aqui un fondo de verdad, ~90)
# foot_x: x de los pies respecto a las manos (negativo = detras); lean: grados que el brazo se inclina hacia atras ARRIBA (0 = hombro justo sobre la muñeca)
# head_gap: hueco entre la cabeza y el suelo ABAJO (la cabeza casi toca); legB: angulo de la pierna abajo (0 = se calcula para que la cabeza quede a head_gap)
# headd / headdB: grados que la cabeza gira respecto al tronco arriba / abajo (cuello neutro, mirada al suelo); far_dx / far_foot_dx: mano y pie lejanos, algo detras
# foot / footF: angulo del pie cercano / lejano (0 = plano; 350 = talon un poco levantado); arrow_dx / arrow_len: posicion (delante de la cabeza) y largo de la flecha gris
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
PIKE_MIN_HIP_RISE_FACTOR = 0.25
PIKE_BODY_MAX_DEG = 145
PIKE_HANDS_FEET_MAX_DY_FACTOR = 1.0
PIKE_ARM_GATE_DEG = 145
PIKE_DOWN_ANGLE_DEG = 115
PIKE_UP_ANGLE_DEG = 145
PIKE_ARMED_MIN_HIP_RISE_FACTOR = 0.10
PIKE_ARMED_BODY_MAX_DEG = 165
PIKE_ARMED_HANDS_FEET_MAX_DY_FACTOR = 1.6

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo
LEG = L_THIGH + L_SHIN          # pierna recta
W = np.array([0.0, WY])         # muñeca cercana (FIJA)


def elbow_len(deg):
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


def foot_clear(foot):
    """altura del tobillo sobre el punto mas bajo del pie (mismos margenes que figura.ground_shift)"""
    hp, k, a, he, to = limb_leg(('fk', 235, 235, foot), np.zeros(2))
    return float(a[1] - min(a[1] - 0.07, he[1] - 0.04, to[1] - 0.04))


ANK = np.array([CFG['foot_x'], foot_clear(CFG['foot'])])                             # tobillo cercano (FIJO, pie apoyado en el suelo)
ANKF = np.array([CFG['foot_x'] + CFG['far_foot_dx'], foot_clear(CFG['footF'])])      # tobillo lejano


def hip_of(leg_deg):
    """cadera con la pierna recta de longitud LEG que baja hasta el tobillo fijo con ese angulo"""
    return ANK - LEG * dv(leg_deg)


def circle_hit(c0, r0, c1, r1):
    """cortes de dos circulos; devuelve los dos puntos (o None)"""
    d = np.linalg.norm(c1 - c0)
    if d > r0 + r1 or d < abs(r0 - r1):
        return None
    a = (r0 ** 2 - r1 ** 2 + d ** 2) / (2 * d); h = np.sqrt(max(r0 ** 2 - a ** 2, 0)); u = (c1 - c0) / d
    m = c0 + u * a; p = np.array([-u[1], u[0]])
    return m + p * h, m - p * h


def shoulder_of(H, elb):
    """hombro a 1 torso de la cadera y a la distancia hombro-muñeca que da ese codo; de los dos cortes, el de MAS ARRIBA/delante (pecho abierto)"""
    pts = circle_hit(H, 1.0, W, elbow_len(elb))
    if pts is None:
        return None
    return max(pts, key=lambda p: p[0] + p[1])


def head_low(S, t, headd):
    hd = S + dv(ang(S - S) if False else t + headd) * NECK_HEAD
    return hd[1] - 0.27


def state(leg_deg, elb, headd):
    H = hip_of(leg_deg)
    S = shoulder_of(H, elb)
    if S is None:
        return None
    t = ang(S - H)                                       # angulo cadera -> hombro (el torso apunta hacia abajo y delante)
    return dict(leg=leg_deg, H=H, S=S, t=t, elb=elb, headd=headd)


def elbow_back(S, e):
    """el codo queda detras (hacia los pies) de la recta hombro-muñeca a su altura"""
    xl = S[0] + (W[0] - S[0]) * (S[1] - e[1]) / (S[1] - W[1])
    return e[0] <= xl + 1e-6


def pose(st):
    p = dict(f=1, ground=False, hip=tuple(st['H']), torso=st['t'], head=st['t'] + st['headd'],
             near_leg=('fk', st['leg'], st['leg'], CFG['foot']), far_leg=('fk', ang(ANKF - st['H']), ang(ANKF - st['H']), CFG['footF']))
    HX, HXF = W[0], W[0] + CFG['far_dx']
    S = st['S']
    for bend in ('cw', 'ccw'):                           # los codos van HACIA ATRAS (detras de la recta hombro-muñeca, hacia los pies)
        e, _ = ik2(S, W, L_UA, L_FA, bend)
        if elbow_back(S, e):
            break
    p['near_arm'] = ('ik', (HX, WY), bend); p['far_arm'] = ('ik', (HXF, WY), bend)
    p['near_hand'] = HAND; p['far_hand'] = HAND
    return p


# ARRIBA: brazos estirados algo inclinados hacia atras (hombro sobre/detras de la muñeca); la cadera es el corte mas alto de
# (circulo de 1 torso alrededor del hombro) y (circulo de pierna recta alrededor del tobillo)
S_A = W + elbow_len(CFG['elbA']) * dv(90 + CFG['lean'])
_hit = circle_hit(S_A, 1.0, ANK, LEG)
assert _hit is not None, 'no hay solucion de postura arriba (cambia foot_x/lean)'
H_A = max(_hit, key=lambda p: p[1])
A = dict(leg=ang(ANK - H_A), H=H_A, S=S_A, t=ang(S_A - H_A), elb=CFG['elbA'], headd=CFG['headd'])

# ABAJO: pierna algo menos vertical (la cadera baja y avanza un poco), codo elbB y la cabeza casi tocando el suelo
if CFG['legB']:
    B = state(CFG['legB'], CFG['elbB'], CFG['headdB'])
else:
    cand = []
    for lg in np.arange(A['leg'] - 25, A['leg'] + 25, 0.05):
        s_ = state(lg, CFG['elbB'], CFG['headdB'])
        if s_ is not None:
            hd = s_['S'] + dv(s_['t'] + s_['headd']) * NECK_HEAD
            cand.append((abs(hd[1] - 0.27 - CFG['head_gap']), lg, s_))
    B = min(cand, key=lambda c: c[0])[2]
    assert min(cand, key=lambda c: c[0])[0] < 3e-2, 'no hay postura abajo con la cabeza a head_gap del suelo'
# A MEDIO CAMINO: pierna a medias entre arriba y abajo, codo elbM
M = state((A['leg'] + B['leg']) / 2, CFG['elbM'], (A['headd'] + B['headd']) / 2)
assert M is not None, 'no hay solucion de postura a medio camino'
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
bb = (ax - 0.15, -0.1, ax + 0.15, max(JA['H'][1], JA['hd'][1]) + 0.3)
imgs = render_scene([PA, PM, PB, PM], OUT + 'pike-push-ups', ground_all=False,
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


def feet_low(J):
    lows = []
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        lows += [he[1] - 0.04, to[1] - 0.04, a[1] - 0.07]
    return min(lows)


for nombre, J in (('arriba', JA), ('a medio camino', JM), ('abajo', JB)):
    tor = np.linalg.norm(J['S'] - J['H'])
    rise = (J['H'][1] - J['S'][1]) / tor
    body = ang3(J['S'], J['H'], J['near_leg'][2])
    dy = abs(J['near_arm'][2][1] - J['near_leg'][2][1]) / tor
    kn = ang3(J['H'], J['near_leg'][1], J['near_leg'][2])
    print(f"{nombre:15s}: codo {codo(J,'near'):.0f}° | caderas sobre hombro {rise*100:.0f}% torso (mín {PIKE_MIN_HIP_RISE_FACTOR*100:.0f}%) | "
          f"ángulo hombro-cadera-tobillo {body:.0f}° (máx {PIKE_BODY_MAX_DEG}°) | manos/pies dy {dy*100:.0f}% | rodilla {kn:.0f}° | "
          f"cadera ({J['H'][0]:.2f}, {J['H'][1]:.2f}) hombro ({J['S'][0]:.2f}, {J['S'][1]:.2f}) | cabeza más baja y={J['hd'][1]-0.27:.2f} | "
          f"codo ({J['near_arm'][1][0]:.2f}, {J['near_arm'][1][1]:.2f})")
assert codo(JA, 'near') >= PIKE_ARM_GATE_DEG and codo(JA, 'far') >= PIKE_ARM_GATE_DEG, 'arriba: los brazos deben estar estirados (>=145)'
assert codo(JB, 'near') <= PIKE_DOWN_ANGLE_DEG and codo(JB, 'far') <= PIKE_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar a <=115'
assert PIKE_DOWN_ANGLE_DEG < codo(JM, 'near') < PIKE_UP_ANGLE_DEG, 'a medio camino: entre los dos umbrales'
for J in (JA, JM, JB):
    tor = np.linalg.norm(J['S'] - J['H'])
    assert (J['H'][1] - J['S'][1]) / tor >= PIKE_MIN_HIP_RISE_FACTOR, 'las caderas deben quedar claramente por encima del hombro (>= 0.25 torsos)'
    assert ang3(J['S'], J['H'], J['near_leg'][2]) <= PIKE_BODY_MAX_DEG, 'el cuerpo debe estar doblado en V (hombro-cadera-tobillo <= 145)'
    assert abs(J['near_arm'][2][1] - J['near_leg'][2][1]) / tor <= PIKE_HANDS_FEET_MAX_DY_FACTOR, 'manos y pies a una altura parecida (<= 1.0 torsos)'
    assert ang3(J['H'], J['near_leg'][1], J['near_leg'][2]) > 178, 'piernas rectas'
    assert elbow_back(J['S'], J['near_arm'][1]), 'el codo debe quedar detras de la recta hombro-muñeca (hacia los pies), cambia ccw/cw'
    assert np.allclose(J['near_arm'][2], JA['near_arm'][2], atol=1e-6), 'las manos no se mueven'
    assert np.allclose(J['near_leg'][2], JA['near_leg'][2], atol=1e-6), 'los pies no se mueven'
    assert abs(feet_low(J)) < 3e-3, 'los pies deben apoyar en el suelo'
    assert J['hd'][1] - 0.27 > -0.01, 'la cabeza no puede atravesar el suelo'
print('OK: arriba, abajo y a medio camino coinciden con los umbrales del contador (pikepushup)')
