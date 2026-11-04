"""Elephant steps (pasos de elefante), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Genera DOS GIFs con el mismo muñeco, suelo, flechas y reloj grises que sentadillas / wall-sit / plank:
  - elephant-steps.gif       (slug elephant-steps, counter "elephantsteps", repeticiones)
  - elephant-steps-hold.gif  (slug elephant-steps-hold, counter "elephantstepshold", aguante cronometrado)
SIN cara (ni nariz ni ojo ni oreja: cabeza lisa, plain_head=True, no se usa cara()).

Forma (guias de "elephant walk"): de pie, pies a la anchura de la cadera, te doblas por la CADERA con la espalda relajada y el pecho hacia las
piernas, cabeza colgando, brazos agarrando las espinillas/tobillos. Una pierna queda ESTIRADA y la otra DOBLA la rodilla levantando el talon
(la punta del pie sigue en el suelo); se alternan las piernas como si caminaras en el sitio (cada paso = 1 repeticion).

Como lo mira la app (workout.js): de PERFIL, con hombro-cadera-rodilla del lado mejor visto -> ANGULO DE CADERA (nunca el de rodilla):
  - repeticiones (processElephantSteps, ELEPHANTSTEPS_*): ARMAR de pie (cadera >= 140 e isStandingSideView) durante 800 ms + 600 ms de asentamiento;
    ABAJO cadera <= 32 ; ARRIBA cadera >= 38 (cuenta 1 repeticion). Vaiven corto, sin exigir ponerse de pie entre toques.
  - aguante (checkElephantStepsHold, ELEPHANTSTEPSHOLD_HIP_MAX_DEG): cadera <= 100.
GIF de repeticiones: de pie (flecha gris: doblarse hacia delante) -> paso A (rodilla CERCANA doblada: abajo) -> entre pasos (las dos estiradas, el torso sube: arriba)
-> paso B (rodilla LEJANA doblada: abajo) -> entre pasos -> (bucle) = 2 repeticiones por vuelta, igual contando por el lado cercano o por el lejano. GIF de aguante: de pie (flecha) -> plegado con el reloj gris en las 12 ->
igual con la manecilla avanzada.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), en coordenadas de imagen normalizadas (la app no corrige el
aspecto), para los dos lados (cercano / lejano) y en varios aspectos, y se simula la maquina de estados de processElephantSteps.
Uso: python ex_elephant_steps.py [carpeta_salida] [clave=valor ...]   (genera los dos GIF + PNG de cada fotograma; usar una carpeta temporal para probar)
Parametros: sd_deg / bd_deg (cadera abajo con la pierna que apoya estirada / la que dobla la rodilla), mid_deg (cadera entre pasos), hold_deg (cadera en el aguante), hx_* (x de la cadera),
far_dx (pie lejano respecto al cercano), hand_floor_x / hand_floor_dx (manos al suelo delante de las puntas en los pasos profundos), hand_mid / hand_off (entre pasos agarran la espinilla), head_rel, margin, arrows=0, clock=0, dur*.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(far_dx=-0.14, sd_deg=26.0, bd_deg=12.0, mid_deg=60.0, hold_deg=30.0, hx=-0.40, hand_floor_x=0.78, hand_floor_dx=-0.08, hand_mid=0.45,
           hand_off=0.14, head_rel=12.0, margin=0.36, arrows=1, arc_r=1.40, arc_a0=62.0, arc_a1=10.0,
           clock=1, clock_dx=1.30, clock_dy=0.50, clock_r=0.27,
           durStand=1500, durD=800, durU=800, durHoldA=1200, durHoldB=1400, durHoldC=1400)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
ELEPHANTSTEPS_DOWN_ANGLE_DEG, ELEPHANTSTEPS_UP_ANGLE_DEG = 32, 38
ELEPHANTSTEPS_ARM_ANGLE_DEG, ELEPHANTSTEPS_ARM_STABLE_MS, ELEPHANTSTEPS_ARM_SETTLE_MS = 140, 800, 600
ELEPHANTSTEPS_MIN_REP_SECONDS = 0.25
ELEPHANTSTEPSHOLD_HIP_MAX_DEG = 100
ARM_STANDING_LEG_MIN_TILT_DEG, ARM_STANDING_TORSO_MIN_TILT_DEG = 65, 55

LEG = L_THIGH + L_SHIN - 0.004            # pierna estirada
AN = np.array([0.0, 0.0])                 # tobillo cercano (pie plano)
AF = np.array([CFG['far_dx'], 0.0])       # tobillo lejano (algo por detras)
FOOT_TOE = np.array([0.37, -0.10])        # punta del pie plano respecto al tobillo (figura.limb_leg: to = a + p*0.10 + d*0.37)


def hip_for(ankle, hx):
    """cadera a la altura que deja la pierna que apoya (la estirada) casi recta"""
    return np.array([hx, ankle[1] + np.sqrt(LEG ** 2 - (hx - ankle[0]) ** 2)])


def pivot_ankle(flat_ankle, f_deg):
    """tobillo con el talon levantado: el pie gira sobre la punta (que no se mueve) hasta apuntar f_deg (negativo = hacia abajo)"""
    d = dv(f_deg); p = rot(d, -90)
    return flat_ankle + FOOT_TOE - p * 0.10 - d * 0.37


def knee_of(H, A):
    return ik2(H, A, L_THIGH, L_SHIN, 'ccw')[0]


def make(hx, t, bent=None, dn=None, hf=None):
    """pose plegada: torso a t grados (hombro respecto a la cadera), 'bent' = lado cuya rodilla se dobla (talon levantado) con la cadera a 'dn' grados"""
    H = hip_for(AF if bent == 'near' else AN, hx)
    legs = {}
    for side, A0 in (('near', AN), ('far', AF)):
        if bent == side:
            goal = (t - dn) % 360
            best = None
            for phi in np.linspace(-85, -2, 415):
                a = pivot_ankle(A0, phi)
                err = abs(((ang(knee_of(H, a) - H) % 360) - goal + 180) % 360 - 180)
                if best is None or err < best[0]:
                    best = (err, phi, a)
            legs[side] = (best[2], float(best[1]))
        else:
            legs[side] = (A0, 0.0)
    P = {}
    for side in ('near', 'far'):
        a, phi = legs[side]
        k = knee_of(H, a)
        v = (a - k) / np.linalg.norm(a - k); n = np.array([-v[1], v[0]])
        n = n if n[0] > 0 else -n                                     # normal hacia delante de la espinilla
        if hf is None:        # pasos profundos: manos al SUELO delante de las puntas (brazos casi estirados); la lejana algo mas atras para que se vean las dos
            P[side] = (np.array([CFG['hand_floor_x'] + (CFG['hand_floor_dx'] if side == 'far' else 0.0), -0.03]), 0.0)
        else:                 # entre pasos: manos sobre la espinilla, a la fraccion hf del tobillo hacia la rodilla
            P[side] = (a + (k - a) * hf + n * CFG['hand_off'], ang(v))
    return dict(f=1, ground=True, plain_head=True, hip=tuple(float(x) for x in H), torso=float(t), head=float(t + CFG['head_rel']),
                near_leg=('ik', tuple(legs['near'][0]), 'ccw', legs['near'][1]), far_leg=('ik', tuple(legs['far'][0]), 'ccw', legs['far'][1]),
                near_arm=('ik', tuple(P['near'][0]), 'cw'), far_arm=('ik', tuple(P['far'][0]), 'cw'),
                near_hand=P['near'][1], far_hand=P['far'][1])


def torso_for(hx, deg, bent=None):
    """torso (grados) para que, con la pierna CERCANA estirada, la cadera mida 'deg' grados"""
    H = hip_for(AN, hx)
    return (ang(AN - H) % 360) + deg


def stand():
    H = hip_for(AN, 0.0)
    return dict(f=1, ground=True, plain_head=True, hip=tuple(float(x) for x in H), torso=90, head=90,
                near_leg=('ik', tuple(AN), 'ccw', 0), far_leg=('ik', tuple(AF), 'ccw', 0),
                near_arm=('fk', 268, 274), far_arm=('fk', 262, 268), near_hand=272, far_hand=266)


# ---- poses
HX = CFG['hx']
S_ = stand()
t_A = (ang(AF - hip_for(AF, HX)) % 360) + CFG['sd_deg']      # paso A: la pierna lejana estirada apoya, la CERCANA dobla la rodilla
t_B = (ang(AN - hip_for(AN, HX)) % 360) + CFG['sd_deg']      # paso B: al reves
A_ = make(HX, t_A, bent='near', dn=CFG['bd_deg'])
B_ = make(HX, t_B, bent='far', dn=CFG['bd_deg'])
M_ = make(HX, torso_for(HX, CFG['mid_deg']), hf=CFG['hand_mid'])                 # entre pasos: las dos estiradas y el torso sube un poco
HOLD = make(HX, torso_for(HX, CFG['hold_deg']))              # aguante: las dos estiradas, pecho hacia las piernas

frames_r = [S_, A_, M_, B_, M_]
durs_r = [int(CFG['durStand']), int(CFG['durD']), int(CFG['durU']), int(CFG['durD']), int(CFG['durU'])]
frames_h = [S_, HOLD, HOLD]
durs_h = [int(CFG['durHoldA']), int(CFG['durHoldB']), int(CFG['durHoldC'])]


def js(frames):
    return [shift_J(build_side(p_), ground_shift(build_side(p_))) for p_ in frames]


JR, JH = js(frames_r), js(frames_h)
allp = np.vstack([all_points(J) for J in JR + JH])
x0, x1 = allp[:, 0].min(), allp[:, 0].max(); ytop = allp[:, 1].max()


def flecha_pliegue(pen):
    """flecha gris curva: el cuerpo se dobla hacia delante por la cadera"""
    if CFG['arrows']:
        c = JR[0]['H']
        draw_arrow(pen, (c[0], c[1]), CFG['arc_r'], CFG['arc_a0'], CFG['arc_a1'])


def reloj(hand_deg):
    def draw(pen):
        if not CFG['clock']:
            return
        c = np.array([CFG['clock_dx'], JH[1]['S'][1] + CFG['clock_dy']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


bb_r = (x0 - 0.1, -0.1, max(x1, CFG['arc_r'] * 0.0 + JR[0]['H'][0] + CFG['arc_r']) + 0.1, ytop + 0.15)
bb_h = (x0 - 0.1, -0.1, max(x1, CFG['clock_dx'] + CFG['clock_r']) + 0.2, ytop + 0.15)
imgs_r = render_scene(frames_r, OUT + 'elephant-steps', durations=durs_r, margin=CFG['margin'], bbox_extra=bb_r,
                      extras=[[flecha_pliegue], None, None, None, None])
imgs_h = render_scene(frames_h, OUT + 'elephant-steps-hold', durations=durs_h, margin=CFG['margin'], bbox_extra=bb_h,
                      extras=[[flecha_pliegue], [reloj(90)], [reloj(-10)]])
cv2.imwrite(OUT + 'elephant-steps_todos.png', np.vstack([np.hstack(imgs_r[:3]), np.hstack([imgs_r[3], imgs_r[4], imgs_h[1]])]))


# =================================================================== comprobaciones contra el contador (workout.js)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def tilt(p, q):
    d = q - p
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


xc = (allp[:, 0].min() + allp[:, 0].max()) / 2
Wf = (allp[:, 0].max() - allp[:, 0].min()) / 0.85


def make_img(aspect):
    Hf = Wf / aspect

    def img(p):
        return np.array([(p[0] - xc) / Wf + 0.5, 0.95 - p[1] / Hf])      # x a la derecha, y ABAJO (como MediaPipe)
    return img


def cadera(J, img, side):
    return ang3(img(J['S']), img(J['H']), img(J[side + '_leg'][1]))


def simula(angles, standing_ok, durs):
    """maquina de estados de processElephantSteps, 3 vueltas del GIF: devuelve repeticiones contadas"""
    state, reps, t = None, 0, 0.0
    stable_since, armed_at = None, None
    for _ in range(3):
        for a, ok, d in zip(angles, standing_ok, durs):
            now = t
            if state is None:
                if a >= ELEPHANTSTEPS_ARM_ANGLE_DEG and ok:
                    stable_since = now if stable_since is None else stable_since
                    if now + d - stable_since >= ELEPHANTSTEPS_ARM_STABLE_MS:        # el fotograma dura lo bastante: armado
                        state, armed_at = 'top', stable_since + ELEPHANTSTEPS_ARM_STABLE_MS
                else:
                    stable_since = None
            elif state == 'top':
                settled = (now + d) - armed_at >= ELEPHANTSTEPS_ARM_SETTLE_MS or now >= armed_at + ELEPHANTSTEPS_ARM_SETTLE_MS
                if a <= ELEPHANTSTEPS_DOWN_ANGLE_DEG and settled:
                    state, rep_start = 'bottom', now
            elif a >= ELEPHANTSTEPS_UP_ANGLE_DEG:
                if (now - rep_start) / 1000 >= ELEPHANTSTEPS_MIN_REP_SECONDS:
                    reps += 1
                state = 'top'
            t += d
    return reps


rangos = {}
for asp in (16 / 9, 4 / 3, 1.0, 3 / 4, 9 / 16):     # 16:9 (apaisado ancho) solo se informa; se exigen 4:3 (webcam), 1:1 y vertical (movil)
    img = make_img(asp)
    for side in ('near', 'far'):
        a_r = [cadera(J, img, side) for J in JR]
        a_h = [cadera(J, img, side) for J in JH]
        rangos[(asp, side)] = (a_r, a_h)
        # de pie para armar
        S, H, K = img(JR[0]['S']), img(JR[0]['H']), img(JR[0][side + '_leg'][1])
        ok_stand = tilt(H, K) >= ARM_STANDING_LEG_MIN_TILT_DEG and tilt(S, H) >= ARM_STANDING_TORSO_MIN_TILT_DEG
        assert a_r[0] >= ELEPHANTSTEPS_ARM_ANGLE_DEG and ok_stand, 'armar: de pie (cadera >= 140 y isStandingSideView) aspecto %.2f %s: %s' % (asp, side, a_r[0])
        assert JR[0] is not None and durs_r[0] >= ELEPHANTSTEPS_ARM_STABLE_MS + ELEPHANTSTEPS_ARM_SETTLE_MS, 'el fotograma de pie debe durar para armar y asentar'
        if asp < 1.5:
            oks = [ok_stand] + [True] * 4
            reps = simula(a_r, oks, durs_r)
            assert reps == 6, 'deben contarse exactamente 2 repeticiones por vuelta (3 vueltas = 6), salen %d (aspecto %.2f, lado %s, angulos %s)' % (reps, asp, side, [round(x) for x in a_r])
            for i in (1, 3):
                assert a_r[i] <= ELEPHANTSTEPS_DOWN_ANGLE_DEG, 'abajo: %.1f' % a_r[i]
            for i in (2, 4):
                assert a_r[i] >= ELEPHANTSTEPS_UP_ANGLE_DEG, 'arriba: %.1f' % a_r[i]
            assert all(x <= ELEPHANTSTEPSHOLD_HIP_MAX_DEG for x in a_h[1:]), 'aguante: cadera <= 100 (%s)' % a_h
            assert a_h[0] > ELEPHANTSTEPSHOLD_HIP_MAX_DEG, 'de pie aun no es la postura del aguante'

for (asp, side), (a_r, a_h) in rangos.items():
    print('aspecto %.2f %-4s | cadera: de pie %5.1f | A(abajo) %5.1f  entre %5.1f  B(abajo) %5.1f  entre %5.1f | aguante %5.1f'
          % (asp, side, a_r[0], a_r[1], a_r[2], a_r[3], a_r[4], a_h[1]))
# --- forma: pies siempre en el suelo con la punta fija, manos sobre las espinillas, sin cara
for J in JR[1:] + JH[1:]:
    assert J['plain_head'], 'cabeza lisa: sin nariz ni ojos'
    for sd in ('near', 'far'):
        hp, kn, an, he, to = J[sd + '_leg']
        assert min(he[1] - 0.04, to[1] - 0.04, an[1] - 0.07) > -2e-3, 'los pies no atraviesan el suelo'
        assert abs((to[1] - 0.04) - (JR[0][sd + '_leg'][4][1] - 0.04)) < 5e-3, 'la punta del pie se queda en el suelo (el talon es lo que sube)'
print('OK: elephant steps coincide con processElephantSteps / checkElephantStepsHold (de pie arma, abajo <= 32, arriba >= 38, aguante <= 100; 2 repeticiones por vuelta)')
