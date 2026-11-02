"""Step ups (subir a un escalon / banco / caja y bajar), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que split-squat / sentadillas / sentadilla bulgara. SIN cara (sin nariz, ojo ni oreja: cabeza lisa, plain_head).
Como lo mira la app (workout.js: processStepUp, bloque STEPUP_*, counter "stepup", slug step-up, migracion 0116): todo es VERTICAL y relativo a una referencia
guardada al armar (de pie en el suelo, quieto, los dos pies a la misma altura); altura de la cadera y de cada tobillo normalizada por el largo de pierna.
Una repeticion cuenta si pasan LAS TRES cosas, en este orden:
  1) un pie en alto y el otro todavia abajo: el tobillo mas alto sube >= STEPUP_FOOT_ON_SURFACE = 0.12 y los dos tobillos difieren >= STEPUP_ASYM_MIN = 0.08,
  2) la cadera SUBE con el cuerpo: >= STEPUP_TOP_HIP_MIN = 0.10 y >= STEPUP_TOP_HIP_FRACTION = 0.6 de lo que subio el pie apoyado (estas de pie ENCIMA),
  3) cadera <= STEPUP_DOWN_HIP = 0.05 y los dos tobillos <= STEPUP_DOWN_ANKLE = 0.05 sobre el suelo otra vez -> has bajado: cuenta (>= STEPUP_MIN_REP_SECONDS = 0.8 s).
Forma correcta (MasterClass, Fitbod, Planfit, UMM Health): de pie delante de un escalon / banco / caja ESTABLE (a la altura de la rodilla o mas bajo), se apoya UN pie
ENTERO encima (la rodilla no pasa de la punta del pie), se empuja con esa pierna (no con la de abajo) hasta quedar de pie sobre la superficie con la pierna estirada y el
otro pie sube y se junta; el tronco va erguido (algo inclinado al subir) y se baja CON CONTROL: el pie de atras baja primero al suelo mientras la pierna de arriba aguanta.
GIF de 5 fotogramas: de pie (suelo) -> pie apoyado en el escalon (flecha gris arriba) -> subiendo (el pie de atras despega) -> arriba (los dos pies en el escalon, de pie)
-> bajando (flecha gris abajo, el pie de atras baja a la punta en el suelo) -> (vuelta al suelo).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), con coordenadas de imagen normalizadas como las ve MediaPipe (la app no corrige
el aspecto) en los aspectos 16:9, 4:3 y 1:1, y se simula la maquina de estados de processStepUp: tiene que contar exactamente 1 repeticion por vuelta.
Uso: python ex_step_up.py [carpeta_salida] [clave=valor ...]   (genera step-ups.gif + PNG de cada fotograma; usar una carpeta temporal para probar)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(box=0.72, bx0=0.62, bx1=1.95, slab=0.13,    # altura del escalon (en largos de torso; ~0.32 del largo de pierna, ~30 cm), x del borde de delante y de atras, grosor de la tapa
           xl=1.10, xt=-0.07, xd=0.90,                 # x del tobillo del pie que SUBE (cercano) sobre el escalon; del pie de atras en el suelo; del pie de atras ya arriba
           tA=90, tB=80, tC=84, tD=90, tE=82, headd=4,  # inclinacion del tronco (90 = erguido; menos = inclinado hacia delante) arriba / apoyado / subiendo / arriba del todo / bajando
           hxB=0.22, hyB=1.97,                         # B (pie apoyado): cadera (x, y); el tobillo de atras sigue en el suelo
           hxC=0.65, hyC=2.52, ankC_x=0.18, ankC_y=0.95, faC=-25,   # C (subiendo): cadera y tobillo de atras en el aire (despega del suelo)
           hxD=1.04, kneeD=172,                        # D (arriba): cadera casi sobre el pie de apoyo; piernas casi rectas
           hxE=0.55, hyE=2.13, faE=-40, ankE_x=0.10,  # E (bajando): cadera; el pie de atras baja con la punta al suelo (talon en el aire)
           hand_dx=0.06, hand_dy=-0.88, far_dx=-0.05, far_dy=0.03, hand=-25,    # manos en las caderas (muñeca respecto al hombro) y direccion de los dedos
           margin=0.26, arrows=1, arrow_gap=0.85, arrow_len=0.5,
           durA=1000, durB=600, durC=500, durD=1100, durE=700)
# kneeD: arriba las piernas casi rectas pero sin bloquear (172°); hyB / hyC / hyE: alturas de cadera elegidas para que la rodilla de apoyo quede ~108° / ~135° / ~100°
# hand_*: la muñeca va pegada a la cadera (se gira con el tronco); far_*: el brazo lejano un pelin distinto para que se vean los dos
# arrow_gap / arrow_len: separacion de la flecha gris respecto a la espalda (por detras del muñeco, a la altura de los hombros) y su largo; arrows=0 las quita
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
STEPUP_MIN_VISIBILITY = 0.5
STEPUP_ARM_STABLE_MS = 700
STEPUP_ARM_SETTLE_MS = 500
STEPUP_ARM_MAX_LEG_DIFF = 0.20
STEPUP_ARM_MAX_ASYM = 0.06
STEPUP_FOOT_ON_SURFACE = 0.12
STEPUP_ASYM_MIN = 0.08
STEPUP_ASYM_WINDOW_MS = 5000
STEPUP_TOP_HIP_MIN = 0.10
STEPUP_TOP_HIP_FRACTION = 0.6
STEPUP_TOP_STABLE_MS = 150
STEPUP_DOWN_HIP = 0.05
STEPUP_DOWN_ANKLE = 0.05
STEPUP_MIN_REP_SECONDS = 0.8
LEG = L_THIGH + L_SHIN


def foot_geom(a, fa):
    """talon y punta de un pie con el tobillo en a y angulo fa (misma geometria que figura.limb_leg)"""
    d = dv(fa); p = rot(d, -90)
    he = a + p * 0.10 - d * 0.07
    return he, he + d * 0.44


def ankle_y(fa):
    """altura del tobillo para que lo mas bajo del pie (con el mismo margen que figura.ground_shift) toque el suelo y = 0"""
    he, to = foot_geom(np.zeros(2), fa)
    return -min(he[1] - 0.04, to[1] - 0.04, -0.07)


def cos_rule(a, b, deg):
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


YF = ankle_y(0)                                  # tobillo con el pie plano en el suelo
BOX = CFG['box']
YB = BOX + YF                                    # tobillo con el pie plano ENCIMA del escalon
H_STAND = LEG * 0.995                            # largo cadera->tobillo con las piernas casi rectas


def hip_above(ankle_xy, hx, knee_deg):
    """altura de la cadera (en x = hx) para que la pierna con ese tobillo quede con la rodilla en 'knee_deg' grados"""
    d = cos_rule(L_THIGH, L_SHIN, knee_deg)
    return float(ankle_xy[1] + np.sqrt(d * d - (ankle_xy[0] - hx) ** 2))


def rot_off(v, t):
    return tuple(rot(np.array(v, float), t - 90))


def pose(hip, t, near, near_fa, far, far_fa):
    """near = pierna que SUBE al escalon (cercana, se dibuja delante), far = pierna de atras; near/far = (x, y) del tobillo"""
    return dict(view='side', f=1, ground=False, plain_head=True, hip=tuple(map(float, hip)), torso=t, head=t + CFG['headd'],
                near_leg=('ik', tuple(map(float, near)), 'ccw', near_fa),
                far_leg=('ik', tuple(map(float, far)), 'ccw', far_fa),
                near_arm=('ikr', rot_off((CFG['hand_dx'], CFG['hand_dy']), t), 'cw'),                       # manos en las caderas, codos hacia atras
                far_arm=('ikr', rot_off((CFG['hand_dx'] + CFG['far_dx'], CFG['hand_dy'] + CFG['far_dy']), t), 'cw'),
                near_hand=CFG['hand'] + (t - 90), far_hand=CFG['hand'] + (t - 90))


XL, XT, XD = CFG['xl'], CFG['xt'], CFG['xd']
NL = np.array([XL, YB])                          # pie que sube, plano sobre el escalon
FT = np.array([XT, YF])                          # pie de atras, plano en el suelo
yD = YB + H_STAND if CFG['kneeD'] >= 180 else hip_above(NL, CFG['hxD'], CFG['kneeD'])
yA = YF + H_STAND

# A: de pie en el suelo, los dos pies a la misma altura (cercano en x = 0, lejano 0.07 por detras para que se vean los dos)
A = pose((0.0, yA), CFG['tA'], (0.0, YF), 0, FT, 0)
# B: pie apoyado en el escalon (rodilla ~108°, sin pasar de la punta); el de atras sigue en el suelo
B = pose((CFG['hxB'], CFG['hyB']), CFG['tB'], NL, 0, FT, 0)
# C: subiendo: la cadera sube, el pie de atras despega y se dobla (talon hacia arriba)
C = pose((CFG['hxC'], CFG['hyC']), CFG['tC'], NL, 0, (CFG['ankC_x'], CFG['ankC_y']), CFG['faC'])
# D: arriba del todo: de pie sobre el escalon, los dos pies encima (el de atras 0.13 mas atras para que se vean los dos)
D = pose((CFG['hxD'], yD), CFG['tD'], NL, 0, (XD, YB), 0)
# E: bajando: el pie de arriba aguanta (rodilla ~100°), el de atras baja hacia el suelo con la punta (talon en el aire)
yE_ank = ankle_y(CFG['faE'])
E = pose((CFG['hxE'], CFG['hyE']), CFG['tE'], NL, 0, (CFG['ankE_x'], yE_ank), CFG['faE'])

frames = [A, B, C, D, E]
durs = [CFG['durA'], CFG['durB'], CFG['durC'], CFG['durD'], CFG['durE']]
JSs = [build_side(p_) for p_ in frames]     # ground=False: ya estan con el suelo en y = 0 (los pies apoyados a mano, ver ankle_y)

# --- escalon (props: se pinta detras del muñeco): caja con tapa, mismo trazo que el banco de la bulgara ------------------------
bx0, bx1 = CFG['bx0'], CFG['bx1']; yb0 = -0.055; yb1 = BOX - 0.055; ys = yb1 - CFG['slab']
PROPS = [('floorbar', bx0, yb1, bx1, yb1), ('floorbar', bx0, yb0, bx1, yb0), ('floorbar', bx0, yb0, bx0, yb1), ('floorbar', bx1, yb0, bx1, yb1),
         ('floorbar', bx0, ys, bx1, ys)]

# flecha gris POR DETRAS de la espalda a la altura de los hombros; alto = rango del hombro
AX = min(J['S'][0] for J in JSs) - CFG['arrow_gap']
Y_LO, Y_HI = min(JSs[1]['S'][1], JSs[4]['S'][1]), JSs[3]['S'][1]


def flecha(subiendo):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (Y_LO + Y_HI) / 2; h = CFG['arrow_len'] / 2
        a, b = (m - h, m + h) if subiendo else (m + h, m - h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


extras = [[], [flecha(True)], [], [], [flecha(False)]]
bb = (AX - 0.15, 0.0, bx1 + 0.12, JSs[3]['hd'][1] + 0.3)
imgs = render_scene(frames, OUT + 'step-ups', props=PROPS, durations=durs, margin=CFG['margin'], bbox_extra=bb, extras=extras, ground_all=False)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processStepUp)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def make_img(aspect):
    """coordenadas de imagen normalizadas como las ve MediaPipe (la app no corrige el aspecto): x / ancho, y / alto (y hacia ABAJO)"""
    return lambda p: np.array([p[0] / aspect, -p[1]])


def lm_of(J, img):
    """landmarks que usa el contador: caderas (las dos en el mismo punto: el muñeco es de perfil) y los dos tobillos"""
    return dict(hip=img(J['H']), a=[img(J['near_leg'][2]), img(J['far_leg'][2])])


def simular(Js_, asp, loops=3):
    """maquina de estados de processStepUp (ref guardada al armar con el fotograma 0; estado 'down'/'up'); cada fotograma dura su tiempo, muestreado cada 50 ms.
    Devuelve (repeticiones, instantes de cada repeticion)"""
    aspect = 1.0 / asp                                  # videoHeight / videoWidth
    img = make_img(asp)
    lms = [lm_of(J, img) for J in Js_]
    dist = lambda a, b: np.hypot(a[0] - b[0], (a[1] - b[1]) * aspect)
    l0 = lms[0]
    legs0 = [dist(l0['hip'], a) for a in l0['a']]
    avg_leg = sum(legs0) / 2
    # armar: las dos piernas parecidas y los dos tobillos a la misma altura
    assert abs(legs0[0] - legs0[1]) <= STEPUP_ARM_MAX_LEG_DIFF * max(legs0), 'armar: las dos piernas deben medir parecido'
    assert abs(l0['a'][0][1] - l0['a'][1][1]) * aspect <= STEPUP_ARM_MAX_ASYM * avg_leg, 'armar: los dos pies a la misma altura (en el suelo)'
    ref = dict(hip=l0['hip'][1], l=l0['a'][0][1], r=l0['a'][1][1], leg=avg_leg)
    state, reps, rep_times = 'down', 0, []
    now, armed_at = 0, 0
    asym_at, surface, rep_start, top_since = None, 0.0, None, None
    seq = [(i, d) for _ in range(loops) for i, d in enumerate(durs)] + [(0, durs[0])]     # + la vuelta final al suelo (la repeticion cuenta al bajar)
    for fi, dur in seq:
        lm = lms[fi]
        hip_rise = (ref['hip'] - lm['hip'][1]) * aspect / ref['leg']
        rise = [(ref['l'] - lm['a'][0][1]) * aspect / ref['leg'], (ref['r'] - lm['a'][1][1]) * aspect / ref['leg']]
        max_rise = max(rise); asym = abs(rise[0] - rise[1])
        for t in range(0, dur, 50):
            tnow = now + t
            if state == 'down':
                if max_rise >= STEPUP_FOOT_ON_SURFACE and asym >= STEPUP_ASYM_MIN:
                    if asym_at is None or tnow - asym_at > STEPUP_ASYM_WINDOW_MS:
                        rep_start = tnow
                    asym_at = tnow; surface = max_rise
                saw = asym_at is not None and tnow - asym_at <= STEPUP_ASYM_WINDOW_MS
                settled = (tnow - armed_at) >= STEPUP_ARM_SETTLE_MS
                need = max(STEPUP_TOP_HIP_MIN, STEPUP_TOP_HIP_FRACTION * surface)
                if settled and saw and hip_rise >= need and max_rise >= STEPUP_FOOT_ON_SURFACE:
                    if top_since is None:
                        top_since = tnow
                    if tnow - top_since >= STEPUP_TOP_STABLE_MS:
                        state = 'up'; top_since = None
                        rep_t0 = rep_start if rep_start is not None else tnow
                else:
                    top_since = None
                    if not saw:
                        asym_at, surface, rep_start = None, 0.0, None
            elif state == 'up':
                if hip_rise <= STEPUP_DOWN_HIP and max_rise <= STEPUP_DOWN_ANKLE:
                    if (tnow - rep_t0) / 1000 >= STEPUP_MIN_REP_SECONDS:
                        reps += 1; rep_times.append(tnow)
                    state = 'down'; asym_at, surface, rep_start, top_since = None, 0.0, None, None
        now += dur
    return reps, rep_times


def medir(J, asp):
    img = make_img(asp); aspect = 1.0 / asp
    dist = lambda a, b: np.hypot(a[0] - b[0], (a[1] - b[1]) * aspect)
    H = img(J['H']); A_ = [img(J['near_leg'][2]), img(J['far_leg'][2])]
    legs = [dist(H, a) for a in A_]
    return H, A_, legs


# valores de referencia del fotograma A (el contador guarda la referencia al armar)
asp0 = 16 / 9
H0, A0, legs0 = medir(JSs[0], asp0)
Lref = sum(legs0) / 2
nombres = ['de pie (suelo)', 'pie apoyado', 'subiendo', 'arriba', 'bajando']
for asp in (16 / 9, 4 / 3, 1.0):
    reps, tms = simular(JSs, asp)
    assert reps == 3, f'el contador debe sumar 1 repeticion por vuelta (aspecto {asp:.2f}: {reps} en 3 vueltas)'
    img = make_img(asp); aspect = 1.0 / asp
    _, A0_, legs_ = medir(JSs[0], asp)
    L = sum(legs_) / 2; Hh = img(JSs[0]['H'])[1]; AL = [A0_[0][1], A0_[1][1]]
    for n_, J in zip(nombres, JSs):
        H_, A_, _ = medir(J, asp)
        hr = (Hh - H_[1]) * aspect / L
        rs = [(AL[0] - A_[0][1]) * aspect / L, (AL[1] - A_[1][1]) * aspect / L]
        if asp == 16 / 9:
            kn = ang3(J['near_leg'][0], J['near_leg'][1], J['near_leg'][2]); kf = ang3(J['far_leg'][0], J['far_leg'][1], J['far_leg'][2])
            print(f"{n_:15s}: cadera +{hr:5.2f} (arriba >= {max(STEPUP_TOP_HIP_MIN, STEPUP_TOP_HIP_FRACTION * (BOX / LEG)):.2f}, abajo <= {STEPUP_DOWN_HIP}) | tobillos {rs[0]:+5.2f}/{rs[1]:+5.2f} "
                  f"(dif {abs(rs[0] - rs[1]):.2f}) | rodilla que sube {kn:5.1f}° atras {kf:5.1f}° | tronco {ang(J['S'] - J['H']):.0f}°")

# --- los tres umbrales con margen, medidos sobre el dibujo (aspecto 16:9)
L = Lref
hr = lambda J: (H0[1] - make_img(asp0)(J['H'])[1]) * (1 / asp0) / L
rs = lambda J: [(A0[i][1] - make_img(asp0)(J[('near' if i == 0 else 'far') + '_leg'][2])[1]) * (1 / asp0) / L for i in (0, 1)]
rB, rC, rD, rE = (rs(J) for J in JSs[1:])
assert max(rB) >= STEPUP_FOOT_ON_SURFACE * 2 and abs(rB[0] - rB[1]) >= STEPUP_ASYM_MIN * 2, 'B: un pie claramente en el escalon y el otro en el suelo'
assert hr(JSs[3]) >= max(STEPUP_TOP_HIP_MIN, STEPUP_TOP_HIP_FRACTION * max(rB)) + 0.05, 'D: la cadera sube con el cuerpo (de pie encima del escalon)'
assert hr(JSs[1]) < STEPUP_TOP_HIP_FRACTION * max(rB), 'B: aun no ha subido la cadera (la cadera no cuenta el apoyo como "arriba")'
assert hr(JSs[4]) < STEPUP_TOP_HIP_FRACTION * max(rB), 'E: bajando, la cadera no esta arriba'
assert max(rE) >= STEPUP_FOOT_ON_SURFACE * 2, 'E: el pie de arriba sigue en el escalon (aun no ha bajado del todo)'

# --- forma: pies sobre el escalon/suelo, rodilla sin pasar de la punta, tronco, piernas, cadera sobre el pie de apoyo arriba
def foot_pts(J, sd):
    hp, kn, an, he, to = J[sd + '_leg']
    return he, to, an, kn


for n_, J in zip(nombres, JSs):
    for sd in ('near', 'far'):
        hp, kn, an, he, to = J[sd + '_leg']
        assert np.linalg.norm(an - hp) < LEG - 1e-3, f'{n_}: la pierna {sd} no llega (cadera-tobillo {np.linalg.norm(an - hp):.3f} >= {LEG:.3f})'
        assert abs(np.linalg.norm(kn - hp) - L_THIGH) < 1e-6 and abs(np.linalg.norm(an - kn) - L_SHIN) < 1e-6, 'huesos con su largo'
    assert J['H'][1] > 0, 'la cadera no atraviesa el suelo'


def low(J, sd):
    hp, kn, an, he, to = J[sd + '_leg']
    return min(he[1] - 0.04, to[1] - 0.04, an[1] - 0.07)


JA_, JB_, JC_, JD_, JE_ = JSs
# pies planos apoyados: A y B (el de atras en el suelo), B/C/D/E (el que sube, encima del escalon), D (los dos arriba), E (el de atras con la punta en el suelo)
assert abs(low(JA_, 'near')) < 3e-3 and abs(low(JA_, 'far')) < 3e-3, 'A: los dos pies tocan el suelo'
assert abs(low(JB_, 'far')) < 3e-3 and abs(low(JB_, 'near') - BOX) < 3e-3, 'B: el de atras en el suelo y el que sube sobre el escalon'
assert low(JC_, 'far') > 0.35, 'C: el pie de atras ya ha despegado del suelo (en el aire)'
assert abs(low(JD_, 'near') - BOX) < 3e-3 and abs(low(JD_, 'far') - BOX) < 3e-3, 'D: los dos pies sobre el escalon'
assert abs(low(JE_, 'far')) < 3e-3 and abs(low(JE_, 'near') - BOX) < 3e-3, 'E: el pie de atras toca el suelo y el otro sigue arriba'
for J in (JB_, JC_, JD_, JE_):
    he, to, an, kn = foot_pts(J, 'near')
    assert abs(an[0] - XL) < 2e-3 and abs(an[1] - YB) < 2e-3, 'el pie de apoyo no se mueve sobre el escalon'
    assert he[0] - 0.04 >= bx0 + 0.15 and to[0] + 0.04 <= bx1 - 0.15, 'el pie esta ENTERO sobre el escalon'
    assert abs(he[1] - to[1]) < 1e-6, 'pie plano sobre el escalon'
for J in (JA_, JB_):
    assert abs(J['far_leg'][2][0] - XT) < 2e-3 and abs(J['far_leg'][2][1] - YF) < 2e-3, 'el pie de atras no se mueve mientras esta en el suelo'
for J in (JB_, JE_):
    kn = J['near_leg'][1]; to = J['near_leg'][4]
    assert kn[0] <= to[0] + 0.05, 'la rodilla de apoyo no pasa de la punta del pie'
assert abs(JD_['far_leg'][2][0] - XD) < 2e-3 and abs(JD_['far_leg'][2][1] - YB) < 2e-3, 'D: el pie de atras sube y se junta'
assert JE_['far_leg'][4][0] + 0.04 < bx0 - 0.1, 'E: la punta del pie que baja queda delante del escalon (no lo atraviesa)'
for J in (JA_, JD_):
    assert abs(ang(J['S'] - J['H']) - 90) < 1e-6, 'tronco erguido arriba y de pie'
    for sd in ('near', 'far'):
        assert ang3(*J[sd + '_leg'][:3]) >= 165, 'piernas casi rectas de pie'
assert abs(JD_['H'][0] - XL) <= 0.20, 'D: la cadera queda sobre el pie de apoyo'
assert 80 <= ang(JB_['S'] - JB_['H']) <= 90 and ang(JC_['S'] - JC_['H']) <= 90, 'el tronco se inclina un poco hacia delante al subir (sin pasarse)'
assert 95 <= ang3(*JB_['near_leg'][:3]) <= 120, 'B: rodilla de apoyo ~100-120°'
assert ang3(*JC_['near_leg'][:3]) > ang3(*JB_['near_leg'][:3]), 'C: la pierna de apoyo se va estirando'
# la rodilla de atras en C / el pie en el aire no atraviesa el escalon: el pie esta por detras del borde o por encima de la tapa
he, to, an, kn = foot_pts(JC_, 'far')
assert to[0] + 0.04 < bx0 or low(JC_, 'far') > BOX, 'C: el pie de atras en el aire no atraviesa el escalon'
print(f"OK: step ups coincide con los umbrales del contador (stepup): pie en alto + cadera sube + vuelta al suelo = 1 repeticion por ciclo (aspectos 16:9, 4:3 y 1:1); "
      f"escalon {BOX:.2f} = {BOX / LEG:.2f} del largo de pierna (>= {STEPUP_FOOT_ON_SURFACE})")
