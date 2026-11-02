"""Sentadillas (squat), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que plank / flexiones / plancha-dinamica. SIN cara (ni nariz ni ojo ni oreja: no se usa cara(), cabeza lisa).
Como lo mira la app (workout.js: processSquat, SQUAT_*, counter "squat", slug squat): de PERFIL, con cadera-rodilla-tobillo del lado mejor visto:
  - ARMAR: de pie de verdad (isStandingSideView): rodilla >= SQUAT_UP_ANGLE_DEG = 160, pierna cadera->tobillo casi vertical (>= 65° sobre la horizontal)
    y tronco erguido (>= 55°),
  - ABAJO: rodilla <= SQUAT_DOWN_ANGLE_DEG = 100,
  - ARRIBA (cuenta 1 repeticion): rodilla >= 160 otra vez.
Forma correcta: pies apoyados enteros en el suelo (NO se mueven), rodillas hacia delante en la direccion de los pies, cadera hacia atras y abajo hasta
que el muslo queda paralelo al suelo, espalda recta con el tronco inclinado hacia delante en paralelo a la espinilla, cabeza en linea con la columna y
brazos estirados al frente como contrapeso.
GIF de 4 fotogramas: de pie (flecha gris abajo) -> bajando -> abajo (muslos paralelos) -> subiendo (flecha gris arriba) -> (vuelta a estar de pie).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), con las medidas en coordenadas de imagen normalizadas
(la app no corrige el aspecto) y se simula la maquina de estados de processSquat: tiene que contar exactamente 1 repeticion por vuelta.
Uso: python ex_sentadillas.py [carpeta_salida] [clave=valor ...]   (genera sentadillas.gif + PNG de cada fotograma; usar una carpeta temporal para probar)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(shinU=270, shinM=259, shinB=250,        # angulo de la espinilla (rodilla->tobillo): 270 = vertical, <270 = rodilla por delante del tobillo
           thighU=270, thighM=316, thighB=2,       # angulo del muslo (cadera->rodilla): 270 = vertical hacia abajo, 0 = horizontal (paralelo al suelo)
           torsoU=90, torsoM=78, torsoB=62,        # inclinacion del tronco sobre la horizontal (90 = erguido)
           headU=90, headM=84, headB=80,           # hacia donde apunta la cabeza (cuello neutro, mirada al frente)
           arm=-4, arm_far=2, far_dx=-0.07, margin=0.34,
           arrows=1, arrow_gap=0.55, arrow_len=0.5,
           durA=1100, durB=600, durC=1200, durD=600)
# shin*/thigh*/torso*/head*: U = de pie, M = a medio camino, B = abajo
# arm / arm_far: angulo de los brazos estirados al frente (0 = horizontal); el lejano un poco distinto para que se vean los dos
# far_dx: el pie/pierna lejanos quedan algo por detras del cercano
# arrow_gap / arrow_len: separacion de la flecha gris respecto a la espalda (por detras del muñeco) y su largo; arrows=0 las quita
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
SQUAT_UP_ANGLE_DEG = 160
SQUAT_DOWN_ANGLE_DEG = 100
ARM_STANDING_LEG_MIN_TILT_DEG = 65
ARM_STANDING_TORSO_MIN_TILT_DEG = 55


def hip_rel(shin, thigh):
    """cadera respecto al tobillo (en (0,0)) para espinilla y muslo con esos angulos"""
    knee = -dv(shin) * L_SHIN
    return knee - dv(thigh) * L_THIGH


def pose(st):
    shin, thigh, torso, head = (CFG['shin' + st], CFG['thigh' + st], CFG['torso' + st], CFG['head' + st])
    hip = hip_rel(shin, thigh)
    return dict(f=1, ground=True, hip=tuple(hip), torso=torso, head=head,
                near_leg=('ik', (0.0, 0.0), 'ccw', 0), far_leg=('ik', (CFG['far_dx'], 0.0), 'ccw', 0),     # pies planos, puntas hacia delante
                near_arm=('fk', CFG['arm'], CFG['arm']), far_arm=('fk', CFG['arm_far'], CFG['arm_far']),
                near_hand=CFG['arm'], far_hand=CFG['arm_far'])


A, M, B = pose('U'), pose('M'), pose('B')
frames = [A, M, B, M]
durs = [CFG['durA'], CFG['durB'], CFG['durC'], CFG['durD']]
JS = [build_side(p_) for p_ in frames]
JSs = [shift_J(J, ground_shift(J)) for J in JS]      # coordenadas con el suelo en y=0 (las mismas que usa render_scene)

# flecha gris POR DETRAS de la espalda (delante van los brazos); alto = rango del hombro entre de pie y abajo
xmin = min(all_points(J)[:, 0].min() for J in JSs)
AX = xmin - CFG['arrow_gap'] + 0.25
Y_LO, Y_HI = JSs[2]['S'][1], JSs[0]['S'][1]


def flecha(bajando):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (Y_LO + Y_HI) / 2; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


extras = [[flecha(True)], [], [], [flecha(False)]]
extras = [extras[0], [], [], extras[3]]
bb = (AX - 0.15, 0.0, AX + 0.15, JSs[0]['hd'][1] + 0.3)
imgs = render_scene(frames, OUT + 'sentadillas', durations=durs, margin=CFG['margin'], bbox_extra=bb, extras=extras)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


allp = np.vstack([all_points(J) for J in JSs])
xc = (allp[:, 0].min() + allp[:, 0].max()) / 2
Wf = (allp[:, 0].max() - allp[:, 0].min()) / 0.85


def make_img(aspect):
    Hf = Wf / aspect

    def img(p):
        return np.array([(p[0] - xc) / Wf + 0.5, 0.90 - p[1] / Hf])      # x a la derecha, y ABAJO (como MediaPipe)
    return img


def tilt(p, q):
    d = q - p
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


def medidas(J, img):
    S, H = img(J['S']), img(J['H'])
    kn, an = img(J['near_leg'][1]), img(J['near_leg'][2])
    return dict(knee=ang3(H, kn, an), leg=tilt(H, an), torso=tilt(S, H))


nombres = ['de pie', 'bajando', 'abajo']
for asp in (16 / 9, 1.0, 4 / 3):
    img = make_img(asp)
    Ms = [medidas(J, img) for J in JSs]
    if asp == 16 / 9:
        for n_, m, J in zip(nombres, Ms[:3], JSs):
            print(f"{n_:8s}: rodilla {m['knee']:5.1f}° | pierna cadera->tobillo {m['leg']:4.1f}° | tronco {m['torso']:4.1f}° | "
                  f"cadera ({J['H'][0]:+.2f}, {J['H'][1]:.2f}) rodilla ({J['near_leg'][1][0]:+.2f}, {J['near_leg'][1][1]:.2f}) punta ({J['near_leg'][4][0]:+.2f})")
    mU, mM, mB, mM2 = Ms
    assert mU['knee'] >= SQUAT_UP_ANGLE_DEG, 'de pie: rodilla >= 160'
    assert mU['leg'] >= ARM_STANDING_LEG_MIN_TILT_DEG and mU['torso'] >= ARM_STANDING_TORSO_MIN_TILT_DEG, 'de pie de verdad (pierna >= 65°, tronco >= 55°)'
    assert mB['knee'] <= SQUAT_DOWN_ANGLE_DEG - 15, 'abajo: rodilla bien por debajo de 100'
    assert SQUAT_DOWN_ANGLE_DEG < mM['knee'] < SQUAT_UP_ANGLE_DEG, 'a medio camino: entre los dos umbrales (no cambia de estado)'
    # --- maquina de estados de processSquat (arma en 'top'; 3 vueltas): 1 repeticion por vuelta
    state, reps = 'top', 0
    for vuelta in range(3):
        for m in (mU, mM, mB, mM2, mU):
            k = m['knee']
            if state == 'top':
                if k <= SQUAT_DOWN_ANGLE_DEG:
                    state = 'bottom'
            elif k >= SQUAT_UP_ANGLE_DEG:
                reps += 1; state = 'top'
    assert reps == 3, f'el contador debe sumar 1 repeticion por vuelta (aspecto {asp:.2f}: {reps} en 3 vueltas)'

# --- forma: pies fijos y en el suelo, rodilla hacia delante sin pasarse de la punta, espalda recta, muslo paralelo abajo
J0 = JSs[0]
for J in JSs:
    for sd in ('near', 'far'):
        hp, kn, an, he, to = J[sd + '_leg']
        assert abs(min(he[1] - 0.04, to[1] - 0.04, an[1] - 0.07)) < 3e-3, 'los pies deben tocar el suelo'
        assert abs(an[0] - J0[sd + '_leg'][2][0]) < 2e-3 and abs(to[0] - J0[sd + '_leg'][4][0]) < 2e-3, 'los pies no se mueven'
    kn, to = J['near_leg'][1], J['near_leg'][4]
    assert kn[0] > J['near_leg'][2][0] - 1e-6, 'rodillas hacia delante (no hacia dentro de la espinilla)'
    assert kn[0] <= to[0] + 0.02, 'la rodilla no pasa de la punta del pie'
    # espalda recta: el cuello/cabeza siguen la linea del tronco (<= 25° de diferencia)
    assert abs(J['hdir'] - (np.rad2deg(np.arctan2(*(J['S'] - J['H'])[::-1])))) <= 28, 'cabeza en linea con la columna'
hB, knB = JSs[2]['H'], JSs[2]['near_leg'][1]
assert hB[1] <= knB[1] + 0.07, 'abajo: la cadera llega al nivel de la rodilla (muslo paralelo)'
print(f"OK: sentadillas coincide con los umbrales del contador (squat): de pie rodilla {medidas(JSs[0], make_img(16/9))['knee']:.0f}° (>= {SQUAT_UP_ANGLE_DEG}), "
      f"abajo {medidas(JSs[2], make_img(16/9))['knee']:.0f}° (<= {SQUAT_DOWN_ANGLE_DEG}); 1 repeticion por ciclo (aspectos 16:9, 4:3 y 1:1)")
