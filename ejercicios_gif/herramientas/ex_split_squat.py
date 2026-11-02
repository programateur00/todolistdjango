"""Split squat (zancada estatica), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que sentadillas / plank / flexiones. SIN cara (ni nariz ni ojo ni oreja: no se usa cara(), cabeza lisa).
Como lo mira la app (workout.js: processSplitSquat, SPLITSQUAT_*, counter "splitsquat", slug split-squat, migracion 0036): de PERFIL, con el angulo
cadera-rodilla-tobillo de cada pierna; la app usa el MINIMO de las dos (la mas doblada):
  - ARMAR: de pie y quieto SPLITSQUAT_STABLE_MS = 800: rodilla (minima) >= SPLITSQUAT_ARM_GATE_ANGLE_DEG = 145 y las dos piernas cadera->tobillo
    inclinadas >= SPLITSQUAT_ARM_MIN_LEG_TILT_DEG = 40° sobre la horizontal (de pie recto con los pies juntos tambien arma),
  - ABAJO: rodilla minima <= SPLITSQUAT_DOWN_ANGLE_DEG = 100 Y la OTRA pierna tambien doblada (<= SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG = 150): las DOS rodillas se doblan
    a la vez (si solo se dobla una, con la otra recta, no cuenta: es un curl de pie, no un split squat),
  - ARRIBA (cuenta 1 repeticion): rodilla minima >= SPLITSQUAT_UP_ANGLE_DEG = 160 otra vez (las dos piernas casi rectas).
Forma correcta (Nike "How to do a split squat", Garage Gym Reviews, Fitbod): se empieza DE PIE, recto, con los pies juntos; se da un paso atras con una pierna
(apoyada en la punta, talon levantado) y el pie de delante queda plano; tronco ERGUIDO todo el rato, manos en las caderas; se baja en vertical hasta que las dos
rodillas llegan a ~90°: muslo delantero paralelo al suelo con la espinilla casi vertical (la rodilla no pasa de la punta del pie) y la rodilla de atras a un palmo
del suelo; se sube empujando con el pie de delante hasta estirar las dos piernas y se vuelve a juntar los pies (posicion inicial).
GIF de 8 fotogramas: 1 DE PIE RECTO, PIES JUNTOS (posicion inicial) -> 2 paso atras -> 3 zancada arriba -> 4 bajando (flecha gris abajo) -> 5 abajo (90°, rodilla de atras casi
en el suelo) -> 6 subiendo (flecha gris arriba) -> 7 zancada arriba -> 8 pie de atras vuelve -> (otra vez el 1).
El pie delantero no se mueve en ningun fotograma; en la zancada (3-7) la PUNTA del pie de atras tampoco (el talon sube al bajar y vuelve a bajar al subir).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), con las medidas en coordenadas de imagen normalizadas
(la app no corrige el aspecto) y se simula la maquina de estados de processSplitSquat: tiene que contar exactamente 1 repeticion por vuelta.
Uso: python ex_split_squat.py [carpeta_salida] [clave=valor ...]   (genera split-squat.gif + PNG de cada fotograma; usar una carpeta temporal para probar)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(xf=0.90, xr=-0.90,          # x del tobillo delantero (FIJO en todo el GIF) y del trasero CON EL PIE PLANO en la zancada; la cadera esta en x = 0 en la zancada
           frearM=-17, frearB=-35,     # angulo del pie de atras a medio camino / abajo (0 = plano; la PUNTA no se mueve y el talon va subiendo)
           frearS=-35,                 # angulo del pie de atras en el paso (punta en el suelo, talon levantado)
           kneeU=168, kneeB=90,        # angulo de la rodilla delantera arriba / abajo (la de atras sale de la geometria)
           together=0.07,              # de pie con los pies juntos: el pie lejano queda este tanto por detras del cercano (para que se vean los dos)
           torso=90, head=90,          # tronco erguido y cuello neutro, mirada al frente
           hand_dx=0.06, hand_dy=-0.88, far_dx=-0.05, far_dy=0.03, hand=-25,   # manos en las caderas (muñeca respecto al hombro) y direccion de los dedos
           margin=0.34, arrows=1, arrow_gap=0.85, arrow_len=0.5,
           durS=1500, durStep=500, durUp=700, durM=450, durB=1100)
# xf / xr: zancada de ~1.8 largos de torso entre los tobillos: arriba las dos piernas quedan casi rectas y abajo salen ~90° delante
# kneeU / kneeB: la app arma con >= 145 (la cuenta de arriba pide >= 160) y baja con <= 100; abajo se dibuja ~90°
# frearM / frearB / frearS: el pie de atras gira sobre la punta: plano en la zancada de arriba, talon cada vez mas alto al bajar
# hand_*: la muñeca va pegada a la cadera, el codo hacia atras (manos en las caderas); far_*: el brazo lejano un pelin distinto para que se vean los dos
# arrow_gap / arrow_len: separacion de la flecha gris respecto a la espalda (por detras del muñeco, a la altura de los hombros) y su largo; arrows=0 las quita
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
SPLITSQUAT_UP_ANGLE_DEG = 160
SPLITSQUAT_DOWN_ANGLE_DEG = 100
SPLITSQUAT_ARM_GATE_ANGLE_DEG = 160 - 15
SPLITSQUAT_ARM_MIN_LEG_TILT_DEG = 40
SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG = 150


def foot_geom(a, fa):
    """talon y punta de un pie con el tobillo en a y angulo fa (misma geometria que figura.limb_leg)"""
    d = dv(fa); p = rot(d, -90)
    he = a + p * 0.10 - d * 0.07
    return he, he + d * 0.44


def ankle_y(fa):
    """altura del tobillo para que lo mas bajo del pie (con el mismo margen que figura.ground_shift) toque el suelo y = 0"""
    he, to = foot_geom(np.zeros(2), fa)
    return -min(he[1] - 0.04, to[1] - 0.04, -0.07)


YF = ankle_y(0)                                  # altura del tobillo con el pie plano
AF = np.array([CFG['xf'], YF])                   # tobillo delantero (fijo)
FLAT_TOE = foot_geom(np.zeros(2), 0)[1]          # punta respecto al tobillo con el pie plano
TOE_R = np.array([CFG['xr'], YF]) + FLAT_TOE     # punta del pie de atras en la zancada (FIJA de 3 a 7)
TOE_R[1] = 0.04                                  # apoyada en el suelo (punta - 0.04 = 0, como ground_shift)
AFAR0 = np.array([CFG['xf'] - CFG['together'], YF])             # de pie con los pies juntos: pie lejano algo por detras del cercano
TOE_FAR0 = AFAR0 + FLAT_TOE


def toe_ankle(toe, fa):
    """tobillo trasero para un angulo de pie fa con la PUNTA en 'toe' (el talon gira sobre ella)"""
    return np.asarray(toe, float) - foot_geom(np.zeros(2), fa)[1]


def hip_for_knee(dx, target):
    """altura de la cadera para la que la rodilla delantera mide 'target' grados, con el tobillo delantero 'dx' por delante de la cadera"""
    lo, hi = YF + 0.3, YF + L_THIGH + L_SHIN + 0.5
    for _ in range(60):
        m = (lo + hi) / 2; d = np.hypot(dx, m - YF)
        ang = np.degrees(np.arccos(np.clip((L_THIGH ** 2 + L_SHIN ** 2 - d * d) / (2 * L_THIGH * L_SHIN), -1, 1)))
        lo, hi = (lo, m) if ang > target else (m, hi)
    return (lo + hi) / 2


HU, HB = hip_for_knee(CFG['xf'], CFG['kneeU']), hip_for_knee(CFG['xf'], CFG['kneeB'])
HM = (HU + HB) / 2
H_STAND = YF + 0.995 * (L_THIGH + L_SHIN)                         # de pie recto: las piernas casi del todo estiradas, el tobillo justo bajo la cadera
HX_STAND = CFG['xf']                                              # (el pie delantero no se mueve: la cadera se desplaza hacia atras al dar el paso)
HX_STEP = CFG['xf'] / 2
H_STEP = hip_for_knee(CFG['xf'] - HX_STEP, 172)
TOE_STEP = np.array([(TOE_FAR0[0] + TOE_R[0]) / 2, 0.04])        # el pie de atras a medio paso: arrastra la punta hacia atras con el talon levantado


def pose(hx, h, far_ankle, far_foot):
    return dict(f=1, ground=False, hip=(hx, h), torso=CFG['torso'], head=CFG['head'],
                near_leg=('ik', tuple(AF), 'ccw', 0),                                  # pierna delantera (cercana): pie plano, rodilla hacia delante
                far_leg=('ik', tuple(far_ankle), 'ccw', far_foot),                     # pierna trasera (lejana)
                near_arm=('ikr', (CFG['hand_dx'], CFG['hand_dy']), 'cw'),               # manos en las caderas, codos hacia atras
                far_arm=('ikr', (CFG['hand_dx'] + CFG['far_dx'], CFG['hand_dy'] + CFG['far_dy']), 'cw'),
                near_hand=CFG['hand'], far_hand=CFG['hand'])


F_STAND = pose(HX_STAND, H_STAND, AFAR0, 0)                                          # 1 de pie recto, pies juntos
F_STEP = pose(HX_STEP, H_STEP, toe_ankle(TOE_STEP, CFG['frearS']), CFG['frearS'])    # 2 / 8 el pie de atras a medio paso
F_TOP = pose(0.0, HU, toe_ankle(TOE_R, 0), 0)                                        # 3 / 7 zancada arriba, pies planos
F_MID = pose(0.0, HM, toe_ankle(TOE_R, CFG['frearM']), CFG['frearM'])                # 4 / 6 a medio camino
F_BOT = pose(0.0, HB, toe_ankle(TOE_R, CFG['frearB']), CFG['frearB'])                # 5 abajo: talon de atras levantado
frames = [F_STAND, F_STEP, F_TOP, F_MID, F_BOT, F_MID, F_TOP, F_STEP]
durs = [CFG['durS'], CFG['durStep'], CFG['durUp'], CFG['durM'], CFG['durB'], CFG['durM'], CFG['durUp'], CFG['durStep']]
I_STAND, I_STEP, I_TOP, I_MID, I_BOT = 0, 1, 2, 3, 4
JSs = [build_side(p_) for p_ in frames]     # ground=False: ya estan con el suelo en y = 0 (los pies apoyados a mano, ver ankle_y / TOE_R)

# flecha gris POR DETRAS de la espalda a la altura de los hombros (por encima de la pierna trasera); alto = rango del hombro entre arriba y abajo
AX = min(J['S'][0] for J in JSs) - CFG['arrow_gap']
Y_LO, Y_HI = JSs[I_BOT]['S'][1], JSs[I_TOP]['S'][1]


def flecha(bajando):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (Y_LO + Y_HI) / 2; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


extras = [[], [], [], [flecha(True)], [], [flecha(False)], [], []]       # posicion inicial limpia; flechas solo al bajar / subir
bb = (AX - 0.15, 0.0, AX + 0.15, JSs[0]['hd'][1] + 0.3)
imgs = render_scene(frames, OUT + 'split-squat', durations=durs, margin=CFG['margin'], bbox_extra=bb, extras=extras, ground_all=False)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processSplitSquat)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def tilt(p, q):
    d = q - p
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


def make_img(aspect):
    """coordenadas de imagen normalizadas como las ve MediaPipe (la app no corrige el aspecto): x / ancho, y / alto (y hacia ABAJO)"""
    return lambda p: np.array([p[0] / aspect, -p[1]])


def medidas(J, img):
    out = {}
    for sd in ('near', 'far'):
        hp, kn, an = J[sd + '_leg'][:3]
        out[sd] = dict(knee=ang3(img(hp), img(kn), img(an)), leg=tilt(img(hp), img(an)))
    out['min'] = min(out['near']['knee'], out['far']['knee'])
    out['max'] = max(out['near']['knee'], out['far']['knee'])
    out['tilts'] = [out['near']['leg'], out['far']['leg']]
    return out


nombres = ['de pie recto', 'paso atras', 'zancada arriba', 'bajando', 'abajo']
for asp in (16 / 9, 4 / 3, 1.0):
    img = make_img(asp)
    Ms = [medidas(J, img) for J in JSs]
    if asp == 16 / 9:
        for n_, m, J in zip(nombres, Ms[:5], JSs):
            print(f"{n_:15s}: rodilla delantera {m['near']['knee']:5.1f}° trasera {m['far']['knee']:5.1f}° (minima {m['min']:5.1f}°) | pierna delantera {m['near']['leg']:4.1f}° trasera {m['far']['leg']:4.1f}° sobre la horizontal | "
                  f"cadera ({J['H'][0]:+.2f}, {J['H'][1]:.2f}) rodilla trasera y {J['far_leg'][1][1]:.2f} rodilla delantera x {J['near_leg'][1][0]:+.2f} (tobillo {J['near_leg'][2][0]:+.2f}, punta {J['near_leg'][4][0]:+.2f})")
    # --- armar (de pie recto, pies juntos, o en la zancada de arriba): rodilla minima >= 145 y las dos piernas inclinadas >= 40°
    for i in (I_STAND, I_TOP):
        assert Ms[i]['min'] >= SPLITSQUAT_ARM_GATE_ANGLE_DEG and min(Ms[i]['tilts']) >= SPLITSQUAT_ARM_MIN_LEG_TILT_DEG, f'fotograma {i + 1}: armar (rodilla >= 145 y piernas >= 40° sobre la horizontal)'
        assert Ms[i]['min'] >= SPLITSQUAT_UP_ANGLE_DEG, f"fotograma {i + 1}: rodilla minima >= 160 (aspecto {asp:.2f}: {Ms[i]['min']:.0f})"
    # --- abajo: minima <= 100 (con margen) y la otra pierna tambien doblada (<= 150): las DOS rodillas se doblan
    mB = Ms[I_BOT]
    assert mB['min'] <= SPLITSQUAT_DOWN_ANGLE_DEG - 5, f"abajo: rodilla minima bien por debajo de 100 (aspecto {asp:.2f}: {mB['min']:.0f})"
    assert mB['max'] <= SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG - 15, 'abajo: la otra pierna tambien doblada (<= 150, con margen)'
    # --- a medio camino (bajando / subiendo) y en el paso: ni abajo (minima > 100, con margen) ni arriba (minima < 160): no cambia de estado ni cuenta nada
    for i in (I_MID, 5):
        assert SPLITSQUAT_DOWN_ANGLE_DEG < Ms[i]['min'] < SPLITSQUAT_UP_ANGLE_DEG, f"medio: entre los dos umbrales (aspecto {asp:.2f}: {Ms[i]['min']:.0f})"
    for i in (I_STEP, 7):
        assert Ms[i]['min'] > SPLITSQUAT_DOWN_ANGLE_DEG + 5, f"paso atras: ni de lejos 'abajo' (aspecto {asp:.2f}: {Ms[i]['min']:.0f})"
        assert Ms[i]['max'] > SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG, 'paso atras: una pierna recta (no puede contar como abajo)'
    # --- maquina de estados de processSplitSquat (se arma de pie; 3 vueltas del GIF): 1 repeticion por vuelta
    state, reps = None, 0
    for vuelta in range(3):
        for m in Ms:
            if state is None:
                if m['min'] >= SPLITSQUAT_ARM_GATE_ANGLE_DEG and min(m['tilts']) >= SPLITSQUAT_ARM_MIN_LEG_TILT_DEG:
                    state = 'top'
            elif state == 'top':
                if m['min'] <= SPLITSQUAT_DOWN_ANGLE_DEG and m['max'] <= SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG:
                    state = 'bottom'
            elif m['min'] >= SPLITSQUAT_UP_ANGLE_DEG:
                reps += 1; state = 'top'
    assert reps == 3, f'el contador debe sumar 1 repeticion por vuelta (aspecto {asp:.2f}: {reps} en 3 vueltas)'

# --- forma
for i, J in enumerate(JSs):
    for sd in ('near', 'far'):
        hp, kn, an, he, to = J[sd + '_leg']
        assert abs(min(he[1] - 0.04, to[1] - 0.04, an[1] - 0.07)) < 3e-3, f'fotograma {i + 1}: los pies deben tocar el suelo'
        assert abs(np.linalg.norm(kn - hp) - L_THIGH) < 1e-6 and abs(np.linalg.norm(an - kn) - L_SHIN) < 1e-6, f'fotograma {i + 1}: huesos con su largo (el tobillo alcanza el suelo sin estirar la pierna)'
    assert abs(J['near_leg'][2][0] - CFG['xf']) < 2e-3, f'fotograma {i + 1}: el pie delantero no se mueve'
    assert abs(J['near_leg'][3][1] - J['near_leg'][4][1]) < 0.03, f'fotograma {i + 1}: pie delantero plano'
    assert J['near_leg'][1][0] <= J['near_leg'][4][0] + 0.02, f'fotograma {i + 1}: la rodilla delantera no pasa de la punta del pie'
    assert abs(ang(J['S'] - J['H']) - 90) < 1e-6, f'fotograma {i + 1}: tronco erguido'
# zancada (3-7): la punta del pie de atras no se mueve
for i in range(2, 7):
    to = JSs[i]['far_leg'][4]
    assert np.allclose(to, JSs[2]['far_leg'][4], atol=2e-3), f'fotograma {i + 1}: la punta del pie de atras no se mueve'
    assert abs(JSs[i]['H'][0]) < 1e-9, f'fotograma {i + 1}: en la zancada la cadera solo sube y baja en vertical'
# --- fotograma 1: de pie, completamente recto y con los pies JUNTOS
J1 = JSs[I_STAND]
m1 = medidas(J1, make_img(16 / 9))
assert abs(J1['H'][0] - J1['near_leg'][2][0]) < 1e-6 and abs(J1['S'][0] - J1['H'][0]) < 1e-6, 'de pie: hombro, cadera y tobillo en la misma vertical'
assert abs(J1['near_leg'][2][0] - J1['far_leg'][2][0]) <= 0.12, 'de pie: los pies juntos (tobillos a menos de 0.12 troncos)'
assert abs(J1['far_leg'][3][1] - J1['far_leg'][4][1]) < 0.03, 'de pie: los dos pies planos'
assert min(m1['near']['knee'], m1['far']['knee']) >= 172, 'de pie: las dos piernas rectas'
# --- zancada arriba: pies planos; abajo: talon de atras levantado, rodilla de atras casi en el suelo, muslo delantero paralelo, espinilla casi vertical
JT, JB = JSs[I_TOP], JSs[I_BOT]
assert abs(JT['far_leg'][3][1] - JT['far_leg'][4][1]) < 0.03, 'zancada arriba: pie de atras plano'
assert JB['far_leg'][3][1] > JB['far_leg'][4][1] + 0.12, 'abajo: talon de atras levantado, apoyado en la punta'
kr, kf = JB['far_leg'][1], JB['near_leg'][1]
assert 0.12 <= kr[1] <= 0.33, f'abajo: la rodilla de atras queda a un palmo del suelo (y={kr[1]:.2f})'
assert abs(kf[1] - JB['H'][1]) < 0.12, 'abajo: muslo delantero paralelo al suelo (rodilla a la altura de la cadera)'
assert abs(ang(JB['near_leg'][2] - kf) + 90) < 22, 'abajo: la espinilla delantera casi vertical'
m16 = [medidas(J, make_img(16 / 9)) for J in JSs]
print(f"OK: split squat coincide con los umbrales del contador (splitsquat): de pie / zancada arriba min {m16[0]['min']:.0f}° / {m16[2]['min']:.0f}° (>= {SPLITSQUAT_UP_ANGLE_DEG}), "
      f"abajo min {m16[4]['min']:.0f}° (<= {SPLITSQUAT_DOWN_ANGLE_DEG}) y la otra {m16[4]['max']:.0f}° (<= {SPLITSQUAT_SUPPORT_MAX_ANGLE_DEG}); 1 repeticion por ciclo (aspectos 16:9, 4:3 y 1:1)")
