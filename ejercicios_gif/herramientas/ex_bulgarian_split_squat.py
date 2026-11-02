"""Sentadilla búlgara (bulgarian split squat), vista de PERFIL mirando a la derecha: pie DELANTERO plano en el suelo, pie TRASERO con el empeine
apoyado en un banco (talón hacia arriba, puntas hacia atrás). Mismo muñeco, estilo y montaje que el resto de GIFs de ejercicios_gif (figura.py),
pero con la cabeza LISA (plain_head): sin nariz, sin ojo, sin oreja.
La app la cuenta con el contador "splitsquat" (slug bulgarian-split-squat, migración 0104; processSplitSquat en workout.js), que mide en directo:
  - ANGULO DE RODILLA (cadera-rodilla-tobillo) de cada pierna visible y se queda con el MINIMO: ARRIBA >= SPLITSQUAT_UP_ANGLE_DEG = 160,
    ABAJO <= SPLITSQUAT_DOWN_ANGLE_DEG = 100; la repeticion cuenta al volver arriba tras haber pasado por abajo (entre 100 y 160 no cambia nada),
  - la OTRA pierna (la trasera) tiene que estar algo doblada abajo: <= SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG = 150 (si no, seria un curl de pierna suelto),
  - para ARMAR (de pie quieto): rodilla minima >= SPLITSQUAT_ARM_GATE_ANGLE_DEG = 145 y las dos piernas (cadera->tobillo) a >= SPLITSQUAT_ARM_MIN_LEG_TILT_DEG = 40°
    de la horizontal (por eso el banco es bajo y la zancada no demasiado larga: con el pie trasero muy alto la pierna de atras quedaria mas tumbada de 40°).
GIF de 4 fotogramas: arriba (las dos piernas casi rectas) -> bajando (flecha gris abajo) -> abajo (rodilla delantera ~90°, muslo casi paralelo al suelo,
rodilla trasera cerca del suelo) -> subiendo (flecha gris arriba). Los dos pies NO se mueven: el delantero plano en el suelo y el trasero sobre el banco;
la cadera baja y sube resolviendo las piernas con IK. Al final se comprueban los umbrales del contador (assert).
Uso: python ex_bulgarian_split_squat.py [carpeta_salida] [clave=valor ...]   (genera bulgarian-split-squat.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(thT=172, sgT=84, thM=126, sgM=83, thB=87, sgB=79,      # rodilla delantera (ángulo interior) y ángulo de la espinilla (sobre la horizontal): arriba / medio / abajo
           tT=91, tM=86, tB=79, headd=6,                          # inclinación del tronco (90 = vertical; <90 = inclinado hacia delante) y giro de la cabeza respecto al tronco
           bench=0.66, gap=0.05, rearTop=161, foot=190,           # altura de la tapa del banco; holgura pie-banco; ángulo de la rodilla trasera arriba; ángulo del pie trasero (190 = puntas atrás y algo abajo)
           ankleF=0.14, armx=0.55, army=-0.40, armcw=1, farx=0.05, fary=-0.05, slab=0.14,   # tobillo delantero (talón en el suelo); muñeca cercana relativa al hombro (por defecto: manos juntas delante del pecho, codos abajo), armcw=0 doblaría el codo al otro lado (con armx=0.10 army=-1.12 = brazos colgando); farx/fary: la lejana respecto a la cercana; grosor del banco
           arrows=1, arrow_dx=0.95, arrow_len=0.80, margin=0.40, bench_l=0.62, bench_r=0.50)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
SPLITSQUAT_UP_ANGLE_DEG = 160
SPLITSQUAT_DOWN_ANGLE_DEG = 100
SPLITSQUAT_ARM_GATE_ANGLE_DEG = 145            # SPLITSQUAT_UP_ANGLE_DEG - SPLITSQUAT_ARM_GATE_TOLERANCE_DEG (15)
SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG = 150
SPLITSQUAT_ARM_MIN_LEG_TILT_DEG = 40
LEG = L_THIGH + L_SHIN

# --- pies fijos ----------------------------------------------------------------------------------------------------------------
AF = np.array([0.0, CFG['ankleF']])             # tobillo delantero (pie plano, punta a la derecha)


def hip_from(th, sg):
    """cadera para una rodilla delantera de 'th' grados con la espinilla a 'sg' grados sobre la horizontal (la rodilla queda delante del tobillo)"""
    K = AF + L_SHIN * dv(sg)
    return K + L_THIGH * dv(sg + 180 - th), K


# pie trasero: el punto más bajo del empeine (pie con la planta hacia arriba) apoya en la tapa del banco
fd = dv(CFG['foot']); p_ = rot(fd, -90)
he0 = p_ * 0.10 - fd * 0.07; to0 = he0 + fd * 0.44
OFF = float(-foot_poly(np.zeros(2), he0, to0, True)[:, 1].min())
RY = CFG['bench'] + CFG['gap'] + OFF            # altura del tobillo trasero


def cos_rule(a, b, deg):
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


HT, _ = hip_from(CFG['thT'], CFG['sgT'])
d_top = cos_rule(L_THIGH, L_SHIN, CFG['rearTop'])
XB = float(HT[0] - np.sqrt(d_top ** 2 - (HT[1] - RY) ** 2))      # x del tobillo trasero: arriba la pierna trasera queda con 'rearTop' grados
AR = np.array([XB, RY])


def pose(th, sg, t):
    H, K = hip_from(th, sg)
    return dict(view='side', f=1, ground=False, plain_head=True, hip=tuple(H), torso=t, head=t + CFG['headd'],
                near_arm=('ikr', (CFG['armx'], CFG['army']), 'cw' if CFG['armcw'] else 'ccw'),
                far_arm=('ikr', (CFG['armx'] + CFG['farx'], CFG['army'] + CFG['fary']), 'cw' if CFG['armcw'] else 'ccw'),
                near_hand=-85, far_hand=-85,
                near_leg=('ikr', tuple(AF - H), 'ccw', 0),                       # delantera: pie plano
                far_leg=('ikr', tuple(AR - H), 'ccw', CFG['foot'], True))        # trasera: empeine en el banco (5º elemento = planta hacia arriba)


A = pose(CFG['thT'], CFG['sgT'], CFG['tT'])
B = pose(CFG['thM'], CFG['sgM'], CFG['tM'])
C = pose(CFG['thB'], CFG['sgB'], CFG['tB'])

# --- banco (props: se pinta detrás del muñeco) -----------------------------------------------------------------------------------
xl, xr = XB - CFG['bench_l'], XB + CFG['bench_r']; yb = CFG['bench']; yt = yb - CFG['slab']
PROPS = [('floorbar', xl, yb, xr, yb), ('floorbar', xl, yt, xr, yt), ('floorbar', xl, yb, xl, yt), ('floorbar', xr, yb, xr, yt),
         ('floorbar', xl + 0.12, yt, xl + 0.12, 0.0), ('floorbar', xr - 0.12, yt, xr - 0.12, 0.0)]


def flecha(bajando, y0, y1, x):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (y0 + y1) / 2; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (x, a), (x, b))
    return f


JA, JB, JC = build_side(A), build_side(B), build_side(C)
ay0, ay1 = JC['H'][1] + 0.2, JA['H'][1] - 0.1                        # la flecha cubre el recorrido de la cadera
ax_ = AF[0] + CFG['arrow_dx']
extras = [None, [flecha(True, ay0, ay1, ax_)], None, [flecha(False, ay0, ay1, ax_)]]
bb = (xl - 0.1, -0.1, ax_ + 0.25, JA['hd'][1] + 0.25)
render_scene([A, B, C, B], OUT + 'bulgarian-split-squat', props=PROPS, floor=True, ground_all=False, extras=extras,
             durations=[1100, 700, 1300, 700], margin=CFG['margin'], bbox_extra=bb)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def deg3(p, q, r):
    a, b = p - q, r - q
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


def tilt(p, q):
    d = q - p
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


def medir(P):
    J = build_side(P); out = {}
    for sd, nm in (('near', 'delantera'), ('far', 'trasera')):
        hp, kn, an, he, to = J[sd + '_leg']
        out[nm] = dict(knee=deg3(hp, kn, an), tilt=tilt(hp, an), ankle=an, knee_pt=kn, toe=to)
    out['torso_tilt'] = tilt(J['H'], J['S'])
    out['min_knee'] = min(out['delantera']['knee'], out['trasera']['knee'])
    out['hip'] = J['H']
    return out


MA, MB, MC = medir(A), medir(B), medir(C)
for nombre, m in (('arriba  (A)', MA), ('a medio (B)', MB), ('abajo   (C)', MC)):
    estado = 'ARRIBA' if m['min_knee'] >= SPLITSQUAT_UP_ANGLE_DEG else ('ABAJO' if m['min_knee'] <= SPLITSQUAT_DOWN_ANGLE_DEG else 'intermedio (no cambia de estado)')
    print(f"{nombre}: rodilla delantera {m['delantera']['knee']:.0f}° / trasera {m['trasera']['knee']:.0f}° (mín {m['min_knee']:.0f}°) -> {estado}; "
          f"inclinación cadera->tobillo {m['delantera']['tilt']:.0f}° / {m['trasera']['tilt']:.0f}°; tronco {m['torso_tilt']:.0f}° sobre la horizontal; cadera y={m['hip'][1]:.2f}")
assert MA['min_knee'] >= SPLITSQUAT_UP_ANGLE_DEG, 'arriba: las dos piernas deben quedar >= 160°'
assert MC['delantera']['knee'] <= SPLITSQUAT_DOWN_ANGLE_DEG, 'abajo: la rodilla delantera debe quedar <= 100°'
assert MC['trasera']['knee'] <= SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG, 'abajo: la pierna trasera tambien debe estar doblada (<= 150°)'
assert SPLITSQUAT_DOWN_ANGLE_DEG < MB['delantera']['knee'] < SPLITSQUAT_UP_ANGLE_DEG, 'a medio camino la rodilla delantera debe estar en la zona intermedia'
assert MA['min_knee'] >= SPLITSQUAT_ARM_GATE_ANGLE_DEG
for nm in ('delantera', 'trasera'):
    assert MA[nm]['tilt'] >= SPLITSQUAT_ARM_MIN_LEG_TILT_DEG, f'arriba: pierna {nm} demasiado tumbada para armar el contador'
# pies quietos: el delantero plano, el trasero sobre el banco
for m in (MA, MB, MC):
    assert np.allclose(m['delantera']['ankle'], AF, atol=2e-3), 'el pie delantero se ha movido (o no alcanza)'
    assert np.allclose(m['trasera']['ankle'], AR, atol=2e-3), 'el pie trasero se ha movido (o no alcanza)'
    assert m['delantera']['knee_pt'][0] <= m['delantera']['toe'][0] + 0.05, 'la rodilla delantera no debe pasar de la punta del pie'
assert MC['trasera']['knee_pt'][1] - 0.135 > 0.0, 'la rodilla trasera no puede atravesar el suelo'
assert MC['delantera']['knee_pt'][1] - 0.05 < MC['hip'][1] + 0.35, 'abajo el muslo delantero debe quedar casi paralelo al suelo'
print(f"pies: delantero ({AF[0]:.2f}, {AF[1]:.2f}) plano; trasero ({AR[0]:.2f}, {AR[1]:.2f}) sobre banco a {CFG['bench']:.2f}; zancada {AF[0] - AR[0]:.2f} (largo de torso)")
print('OK: arriba, intermedio y abajo coinciden con los umbrales del contador (splitsquat)')
