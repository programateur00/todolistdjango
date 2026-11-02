"""Plancha dinamica (dynamic plank, "arriba y abajo"), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que plank.gif / plancha-con-toques-de-hombro.gif / flexiones.gif. SIN cara (ni nariz ni ojo ni oreja: no se usa cara(), cabeza lisa).
Como lo mira la app (workout.js: processDynamicPlank, DYNPLANK_*, counter "dynamicplank", slug dynamic-plank, migracion 0110): de PERFIL, con hombro, codo, muñeca, cadera y
tobillo del lado mejor visto (el brazo medido se fija al armar). UNA REPETICION = plancha ALTA (manos, brazos estirados) -> bajar a los ANTEBRAZOS -> volver a subir a las manos:
  - ARMAR: inclinacion hombro-cadera <= ON_GROUND_MAX_TILT_DEG = 40, hombro-cadera-tobillo >= DYNPLANK_ARM_LINE_MIN_DEG = 140 y codo >= DYNPLANK_ARM_GATE_ANGLE_DEG = 145 (plancha alta),
  - ABAJO: codo <= DYNPLANK_DOWN_ANGLE_DEG = 125 (en antebrazos queda en ~90°),
  - ARRIBA (cuenta 1 repeticion): codo >= DYNPLANK_UP_ANGLE_DEG = 140 otra vez; la serie se cierra si el tronco pasa de PUSHUP_BROKEN_TILT_DEG = 60° de inclinacion.
Los pies NO se mueven (puntas apoyadas): el cuerpo recto gira alrededor de las puntas al bajar y subir. Se baja como en la plancha dinamica real: el codo baja justo donde estaba la mano y el
antebrazo se apoya hacia delante; para subir se apoya la palma donde estaba el codo y se empuja hasta estirar el brazo.
GIF de 4 fotogramas: plancha ALTA (flecha gris abajo) -> bajando -> plancha en ANTEBRAZOS (flecha gris arriba) -> subiendo -> (vuelta a la plancha alta).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), con las medidas en coordenadas de imagen normalizadas (la app no corrige el aspecto) y
se simula la maquina de estados de processDynamicPlank sobre los angulos de codo del ciclo: tiene que contar exactamente 1 repeticion por vuelta.
Uso: python ex_plancha_dinamica.py [carpeta_salida] [clave=valor ...]   (genera plancha-dinamica.gif + PNG de cada fotograma; usar una carpeta temporal para la salida, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, ey=0.095, wy=0.09, far_dx=-0.07, foot=292, footF=296, far_t=1.5, headd=6, margin=0.32,
           fdown=0.5, phi_down=-28.0, fup=0.45, hand_dx=0.0,
           arrows=1, arrow_gap=0.28, arrow_len=0.42, fingers=1, aspect=16 / 9,
           durA=900, durB=450, durC=900, durD=450)
# elbA: angulo del codo en la plancha alta (brazos casi rectos; con la mano justo donde queda el codo en la plancha de antebrazos)
# ey: altura del centro del codo apoyado (el codo toca el suelo); wy: altura de la muñeca con la palma apoyada en el suelo
# far_dx: el brazo LEJANO queda algo detras del cercano (para que se vean los dos)
# foot / footF: angulo del pie cercano / lejano (apoyo en las puntas: ~290 = punta hacia abajo); far_t: grados que la pierna lejana se separa de la cercana
# headd: grados que la cabeza mira por encima de la linea del cuerpo (cuello neutro, mirada al suelo un poco por delante)
# fdown / fup: altura del hombro en el fotograma 'bajando' / 'subiendo' (0 = altura en antebrazos, 1 = altura en plancha alta)
# phi_down: angulo del antebrazo (grados, 0 = horizontal hacia delante) en 'bajando': el codo baja y el antebrazo se apoya hacia delante
# hand_dx: desplazamiento extra en x de las manos de la plancha alta respecto a donde queda el codo en antebrazos
# arrow_gap / arrow_len: x de la flecha gris respecto al punto mas adelantado del dibujo y su largo; arrows=0 las quita; fingers=0 quita las rayitas de los dedos
# aspect: ancho/alto del encuadre de la camara con el que se comprueban los angulos
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
ON_GROUND_MAX_TILT_DEG = 40
PUSHUP_BROKEN_TILT_DEG = 60
DYNPLANK_ARM_LINE_MIN_DEG = 140
DYNPLANK_ARM_GATE_ANGLE_DEG = 145
DYNPLANK_UP_ANGLE_DEG = 140
DYNPLANK_DOWN_ANGLE_DEG = 125
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo


def elbow_len(deg):
    """distancia hombro-muñeca para un angulo de codo dado"""
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


def pose_t(t, hip):
    """cuerpo recto (tabla) con el tronco a t grados sobre la horizontal; los brazos se ponen despues"""
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


# ---- el cuerpo recto apoyado SIEMPRE en las mismas puntas de los pies (toe_x = 0): tabla t -> hombro / cadera ----
_T = np.linspace(2, 60, 5801)
_SH, _HP = [], []
for _t in _T:
    _J = build_side(pose_t(_t, (0.0, 0.0)))
    _d = np.array([0.0 - toe_x(_J), -feet_low(_J)])
    _SH.append(_J['S'] + _d); _HP.append(np.array(_d))
_SH, _HP = np.array(_SH), np.array(_HP)
assert np.all(np.diff(_SH[:, 1]) > 0), 'la altura del hombro debe crecer con la inclinacion'


def body(sy):
    """(t, hombro, cadera) del cuerpo recto con las puntas apoyadas y el hombro a altura sy"""
    i = int(np.argmin(np.abs(_SH[:, 1] - sy)))
    assert abs(_SH[i, 1] - sy) < 2e-3, 'no hay solucion de postura a esa altura del hombro'
    return float(_T[i]), _SH[i].copy(), _HP[i].copy()


dF = float(np.rad2deg(np.arcsin(CFG['far_dx'] / L_UA)))       # brazo lejano: el codo queda far_dx por detras del cercano

# ---- C: plancha en ANTEBRAZOS (como plank.gif): hombro justo sobre el codo, codos a 90° ----
EY, WY = CFG['ey'], CFG['wy']
SY_C = EY + L_UA
tC, SC, HPC = body(SY_C)
XE = float(SC[0])                                          # x del codo / hombro en antebrazos = donde se apoyan las manos en la plancha alta (+ hand_dx)
XH = XE + CFG['hand_dx']

# ---- A: plancha ALTA: muñeca apoyada en (XH, WY); el hombro sube hasta que el codo queda a elbA grados (brazo casi recto) ----
_cand = []
for i in range(len(_T)):
    d = float(np.hypot(_SH[i, 0] - XH, _SH[i, 1] - WY))
    _cand.append(abs(d - elbow_len(CFG['elbA'])))
iA = int(np.argmin(_cand))
assert _cand[iA] < 2e-3, 'no hay solucion de postura en la plancha alta'
tA, SA, HPA = float(_T[iA]), _SH[iA].copy(), _HP[iA].copy()
SY_A = float(SA[1])

# ---- B: bajando; D: subiendo (alturas intermedias) ----
SY_B = SY_C + CFG['fdown'] * (SY_A - SY_C)
SY_D = SY_C + CFG['fup'] * (SY_A - SY_C)
tB, SB, HPB = body(SY_B)
tD, SD, HPD = body(SY_D)


def pose(t, hip, near_arm, far_arm, near_hand=HAND, far_hand=HAND):
    p = pose_t(t, tuple(hip))
    p.update(near_arm=near_arm, far_arm=far_arm, near_hand=near_hand, far_hand=far_hand)
    return p


# A: manos apoyadas bajo (casi) el hombro; la lejana un pelin detras
PA = pose(tA, HPA, ('ik', (XH, WY), 'cw'), ('ik', (XH + CFG['far_dx'], WY), 'cw'))
# C: antebrazos apoyados, hombro sobre el codo (fk como plank.gif)
PC = pose(tC, HPC, ('fk', 270, 0), ('fk', 270 + dF, 0))
# B: bajando: el codo queda en x = XH (donde estaba la mano) y el antebrazo baja hacia delante (phi_down)
_E = np.array([XH, SB[1] - np.sqrt(L_UA ** 2 - (SB[0] - XH) ** 2)])
uB = ang(_E - SB)
_wyB = float(_E[1] + L_FA * np.sin(np.deg2rad(CFG['phi_down'])))                 # altura de la muñeca en 'bajando'
hB = float(np.rad2deg(np.arcsin(np.clip((EY - _wyB) / 0.30, -1, 1))))           # la mano va casi plana: la punta de los dedos no atraviesa el suelo
PB = pose(tB, HPB, ('fk', uB, CFG['phi_down']), ('fk', uB + dF, CFG['phi_down']), near_hand=hB, far_hand=hB)
# D: subiendo: palma apoyada donde estaba el codo, el codo se dobla hacia atras mientras el cuerpo sube
PD = pose(tD, HPD, ('ik', (XH, WY), 'cw'), ('ik', (XH + CFG['far_dx'], WY), 'cw'))
# manos: en los fotogramas con la palma apoyada (A, D) dedos hacia delante; en C la mano va plana sobre el suelo como el antebrazo
frames = [PA, PB, PC, PD]
durs = [CFG['durA'], CFG['durB'], CFG['durC'], CFG['durD']]
JS = [build_side(p_) for p_ in frames]


def dedos(J, sd='near'):
    """rayitas de los dedos sobre la mano apoyada (la mano es un tubo corto; con ellas se lee la palma plana en el suelo)"""
    def f(pen):
        if not CFG['fingers']:
            return
        w_, tip = J[sd + '_arm'][2], J[sd + '_handtip']
        for k_ in (0.12, 0.20):
            x = tip[0] - k_
            pen.line([(x, w_[1] + 0.045), (x, w_[1] + 0.085)], w=pen.c.LI * 0.8)
    return f


xmax = max(all_points(J)[:, 0].max() for J in JS)
AX = xmax + CFG['arrow_gap']
Y_LO, Y_HI = SY_C - 0.05, SY_A + 0.05


def flecha(subiendo):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (Y_LO + Y_HI) / 2; h = CFG['arrow_len'] / 2
        a, b = (m - h, m + h) if subiendo else (m + h, m - h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


extras = [[dedos(JS[0]), flecha(False)], [], [flecha(True)], [dedos(JS[3])]]
bb = (AX - 0.15, 0.0, AX + 0.15, JS[0]['hd'][1] + 0.3)
imgs = render_scene(frames, OUT + 'plancha-dinamica', durations=durs, margin=CFG['margin'], bbox_extra=bb, extras=extras)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


allp = np.vstack([all_points(J) for J in JS])
xc = (allp[:, 0].min() + allp[:, 0].max()) / 2
Wf = (allp[:, 0].max() - allp[:, 0].min()) / 0.85          # el cuerpo ocupa ~85% del ancho del encuadre


def make_img(aspect):
    Hf = Wf / aspect

    def img(p):
        """coordenadas del muñeco (y arriba) -> coordenadas de imagen normalizadas como MediaPipe (x a la derecha, y ABAJO, 0..1; suelo al 80% de la altura)"""
        return np.array([(p[0] - xc) / Wf + 0.5, 0.80 - p[1] / Hf])
    return img


def medidas(J, img):
    S, H = img(J['S']), img(J['H'])
    an = img(J['near_leg'][2])
    e, w_ = img(J['near_arm'][1]), img(J['near_arm'][2])
    d = H - S
    tilt = float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))
    return dict(elbow=ang3(S, e, w_), line=ang3(S, H, an), tilt=tilt)


nombres = ['plancha ALTA', 'bajando', 'ANTEBRAZOS', 'subiendo']
print(f"alturas del hombro: antebrazos {SY_C:.2f} | bajando {SY_B:.2f} | subiendo {SY_D:.2f} | plancha alta {SY_A:.2f} ; tronco {tC:.1f}° / {tB:.1f}° / {tD:.1f}° / {tA:.1f}° ; codo (muñeca de A) en x={XH:.2f}")
for asp in (CFG['aspect'], 1.0, 4 / 3):
    img = make_img(asp)
    M = [medidas(J, img) for J in JS]
    if asp == CFG['aspect']:
        for n_, m, J in zip(nombres, M, JS):
            print(f"{n_:13s}: codo {m['elbow']:5.1f}° | linea hombro-cadera-tobillo {m['line']:5.1f}° | inclinacion {m['tilt']:4.1f}° | "
                  f"muñeca ({J['near_arm'][2][0]:.2f}, {J['near_arm'][2][1]:.2f}) codo ({J['near_arm'][1][0]:.2f}, {J['near_arm'][1][1]:.2f})")
    mA, mB, mC, mD = M
    # --- armar: plancha alta (codo casi recto, cuerpo en linea recta, tumbado de verdad)
    assert mA['elbow'] >= DYNPLANK_ARM_GATE_ANGLE_DEG, f'plancha alta: codo >= {DYNPLANK_ARM_GATE_ANGLE_DEG} (aspecto {asp:.2f})'
    assert mA['line'] >= DYNPLANK_ARM_LINE_MIN_DEG, 'plancha alta: hombro-cadera-tobillo >= 140'
    assert mA['tilt'] <= ON_GROUND_MAX_TILT_DEG, f"plancha alta: inclinacion hombro-cadera <= 40 (aspecto {asp:.2f}: {mA['tilt']:.0f})"
    # --- abajo: antebrazos, codo a ~90 (<= 125)
    assert mC['elbow'] <= DYNPLANK_DOWN_ANGLE_DEG - 20, 'antebrazos: codo muy por debajo de 125'
    assert 80 <= mC['elbow'] <= 100, 'antebrazos: codo a ~90'
    # --- el cuerpo es una tabla y no se rompe la serie en ningun fotograma
    for m in M:
        assert m['line'] >= DYNPLANK_ARM_LINE_MIN_DEG, 'cuerpo en linea recta en todos los fotogramas'
        assert m['tilt'] < PUSHUP_BROKEN_TILT_DEG, 'no se cierra la serie por inclinacion'
    # --- maquina de estados de processDynamicPlank sobre el ciclo (arma en A; 3 vueltas): 1 repeticion por vuelta
    state, reps = 'top', 0
    for vuelta in range(3):
        for m in (mA, mB, mC, mD, mA):
            e = m['elbow']
            if state == 'top':
                if e <= DYNPLANK_DOWN_ANGLE_DEG:
                    state = 'bottom'
            elif e >= DYNPLANK_UP_ANGLE_DEG:
                reps += 1; state = 'top'
        # (el ultimo mA de cada vuelta es el primero de la siguiente: se descuenta)
    assert reps == 3, f'el contador debe sumar 1 repeticion por vuelta (aspecto {asp:.2f}: {reps} en 3 vueltas)'
    assert mD['elbow'] < DYNPLANK_UP_ANGLE_DEG, 'subiendo: aun no cuenta (codo < 140) hasta llegar arriba'
# --- los pies no se mueven y tocan el suelo; las puntas siempre en el mismo sitio
J0 = JS[0]
for J in JS:
    assert abs(feet_low(J)) < 3e-3, 'los pies deben tocar el suelo'
    assert abs(J['near_leg'][4][0] - J0['near_leg'][4][0]) < 2e-3 and abs(J['near_leg'][4][1] - J0['near_leg'][4][1]) < 2e-3, 'los pies no se mueven'
# --- las manos / antebrazos estan en el suelo cuando toca (A, D palma; C antebrazo) y no atraviesan el suelo
for J, n_ in ((JS[0], 'A'), (JS[3], 'D')):
    assert abs(J['near_arm'][2][1] - WY) < 2e-3 and abs(J['far_arm'][2][1] - WY) < 2e-3, f'{n_}: la palma apoyada en el suelo'
assert abs(JS[2]['near_arm'][1][1] - EY) < 2e-3 and abs(JS[2]['near_arm'][2][1] - EY) < 2e-3, 'C: codo y muñeca apoyados (antebrazo plano)'
assert abs(JS[2]['near_arm'][1][0] - JS[2]['S'][0]) < 0.03, 'C: el hombro queda justo sobre el codo'
for J in JS:
    for sd in ('near', 'far'):
        assert J[sd + '_arm'][1][1] - 0.095 >= -3e-3 and J[sd + '_arm'][2][1] - 0.09 >= -3e-3, 'ni el codo ni la muñeca atraviesan el suelo'
        assert J[sd + '_handtip'][1] - 0.09 >= -4e-3, 'la punta de los dedos no atraviesa el suelo'
print(f"OK: plancha dinamica coincide con los umbrales del contador (dynamicplank): arriba codo {medidas(JS[0], make_img(CFG['aspect']))['elbow']:.0f}° (>= {DYNPLANK_ARM_GATE_ANGLE_DEG}), "
      f"abajo {medidas(JS[2], make_img(CFG['aspect']))['elbow']:.0f}° (<= {DYNPLANK_DOWN_ANGLE_DEG}); 1 repeticion por ciclo (aspectos 16:9, 4:3 y 1:1)")
