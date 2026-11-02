"""Sentadillas con salto (jump squat), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones-con-palmada / v-up. SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app (workout.js: processSquat con counter "jumpsquat", slug jump-squat, JUMPSQUAT_*): de PERFIL, de pie -> sentadilla -> salto.
  - ARRIBA / DE PIE: rodilla (cadera-rodilla-tobillo) >= SQUAT_UP_ANGLE_DEG = 160 y de pie de verdad (isStandingSideView: pierna cadera->tobillo
    >= ARM_STANDING_LEG_MIN_TILT_DEG = 65° sobre la horizontal y tronco hombro->cadera >= ARM_STANDING_TORSO_MIN_TILT_DEG = 55°),
  - ABAJO: rodilla <= SQUAT_DOWN_ANGLE_DEG = 100,
  - SALTO (al subir): tobillos o cadera suben sobre su altura de pie >= JUMPSQUAT_LIFT_FACTOR = 0.10 largos de pierna (vertical cadera-tobillo);
    la rep cuenta al estirar la rodilla (>= 160) habiendo visto ese salto en la subida; sin salto no cuenta.
GIF de 4 fotogramas: de pie (flecha abajo) -> abajo (sentadilla, brazos atras para el impulso, flecha arriba) -> EN EL AIRE (cuerpo estirado,
brazos arriba, pies despegados, flecha arriba) -> aterrizaje amortiguado (rodillas flexionadas, brazos adelante, flecha abajo) -> vuelve a «de pie» (bucle).
Los pies (planos) NO se mueven mientras estan en el suelo. Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_sentadilla_salto.py [carpeta_salida] [clave=valor ...]   (genera sentadillas-con-salto.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(kU=168, kB=88, kL=126, leanU=2, leanB=21, leanL=12, tU=88, tB=52, tL=66, headd=14, far_dx=-0.10,
           jump=0.42, air_t=89, air_ua=62, air_fa=58, air_far=3, arrows=1, arrow_dx=1.15, arrow_len=0.5, margin=0.45,
           dur0=1100, dur1=1000, dur2=1100, dur3=800)
# kU/kB/kL: angulo de la rodilla (cadera-rodilla-tobillo) de pie / abajo / al aterrizar (la app: >=160 de pie, <=100 abajo)
# leanU/leanB/leanL: inclinacion de la espinilla hacia delante respecto a la vertical (la rodilla avanza sobre el pie)
# tU/tB/tL: inclinacion del tronco sobre la horizontal (90 = erguido) de pie / abajo / al aterrizar; headd: grados de la cabeza sobre la linea del tronco
# far_dx: cuanto queda el pie lejano por detras del cercano (para que se vean los dos); jump: cuanto sube el cuerpo en el aire (unidades = troncos)
# air_t: inclinacion del tronco en el aire; air_far: grados de mas de la pierna/brazo lejanos en el aire
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
SQUAT_UP_ANGLE_DEG = 160
SQUAT_DOWN_ANGLE_DEG = 100
ARM_STANDING_LEG_MIN_TILT_DEG = 65
ARM_STANDING_TORSO_MIN_TILT_DEG = 55
JUMPSQUAT_LIFT_FACTOR = 0.10

AY = 0.14                        # altura del tobillo con el pie plano apoyado (la suela queda en y=0, como figura.ground_shift)
FOOT_FLAT = 0                    # pie plano: la puntera apunta hacia delante (derecha)


def squat_geom(K, lean):
    """cadera, rodilla y tobillo (cercano) con el pie plano en (0, AY), la espinilla inclinada 'lean' grados hacia delante y rodilla de K grados"""
    A = np.array([0.0, AY])
    knee = A + L_SHIN * np.array([np.sin(np.deg2rad(lean)), np.cos(np.deg2rad(lean))])
    hip = knee + L_THIGH * dv(270 - lean - K)
    return hip, knee, A


def feet_on_floor(hip, bend='ccw'):
    """piernas con IK: tobillo cercano en (0, AY), lejano un poco por detras; pies planos"""
    return dict(near_leg=('ik', (0.0, AY), bend, FOOT_FLAT), far_leg=('ik', (CFG['far_dx'], AY), bend, FOOT_FLAT))


def arms(un, fn, uf, ff):
    """brazos 'fk' (angulos de brazo y antebrazo, cercano y lejano) con las manos siguiendo el antebrazo"""
    return dict(near_arm=('fk', un, fn), far_arm=('fk', uf, ff), near_hand=fn, far_hand=ff)


def pose_floor(K, lean, t, a):
    hip, knee, A = squat_geom(K, lean)
    p = dict(f=1, ground=False, hip=tuple(hip), torso=t, head=t + CFG['headd'])
    p.update(feet_on_floor(hip)); p.update(a)
    return p


# 1) DE PIE: brazos colgando un poco por delante del cuerpo, listo para bajar
A_U = arms(268, 282, 262, 276)
# 2) ABAJO: sentadilla (rodilla ~88°), tronco inclinado y brazos hacia atras para tomar impulso
A_B = arms(222, 212, 228, 218)
# 4) ATERRIZAJE: amortigua con las rodillas flexionadas (~126°) y los brazos hacia delante para el equilibrio
A_L = arms(312, 343, 306, 337)
FU = pose_floor(CFG['kU'], CFG['leanU'], CFG['tU'], A_U)
FB = pose_floor(CFG['kB'], CFG['leanB'], CFG['tB'], A_B)
FL = pose_floor(CFG['kL'], CFG['leanL'], CFG['tL'], A_L)

# 3) EN EL AIRE: cuerpo estirado y erguido, brazos arriba, pies despegados con las puntas hacia abajo
hipU = np.array(FU['hip'])
hipA = hipU + np.array([0.0, CFG['jump']])
TA = CFG['air_t']
FA = dict(f=1, ground=False, hip=tuple(hipA), torso=TA, head=TA + 2,
          near_leg=('fk', 268, 266, 284), far_leg=('fk', 268 + CFG['air_far'] + 1, 266 + CFG['air_far'], 280),
          **arms(CFG['air_ua'], CFG['air_fa'], CFG['air_ua'] + 10 + CFG['air_far'], CFG['air_fa'] + 12 + CFG['air_far']))
FRAMES = [FU, FB, FA, FL]


def flechas(i):
    if not CFG['arrows']:
        return None
    x = CFG['arrow_dx']; L = CFG['arrow_len']
    if i == 0:   # a punto de bajar
        return [lambda pen: draw_line_arrow(pen, (x, 1.55), (x, 1.55 - L))]
    if i == 1:   # impulso hacia arriba
        return [lambda pen: draw_line_arrow(pen, (x, 0.80), (x, 0.80 + L))]
    if i == 2:   # todavia subiendo
        return [lambda pen: draw_line_arrow(pen, (x, 1.45 + CFG['jump'] * 0.5), (x, 1.45 + CFG['jump'] * 0.5 + L))]
    return [lambda pen: draw_line_arrow(pen, (x, 1.35), (x, 1.35 - L))]


render_scene(FRAMES, OUT + 'sentadillas-con-salto', durations=[int(CFG['dur0']), int(CFG['dur1']), int(CFG['dur2']), int(CFG['dur3'])],
             margin=CFG['margin'], extras=[flechas(i) for i in range(4)])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processSquat con jumpsquat)
def angle3(a, b, c):
    """angulo en b (grados) entre b->a y b->c, como angle() de la app"""
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


def tilt(a, b):
    """tiltFromHorizontal de la app (grados sobre la horizontal)"""
    return float(np.degrees(np.arctan2(abs(b[1] - a[1]), abs(b[0] - a[0]))))


Js = [build_side(fr) for fr in FRAMES]
names = ('de pie', 'abajo', 'en el aire', 'aterrizaje')
ref = Js[0]                                            # referencia de pie (jumpRef de la app)
ref_ankle = min(ref[s + '_leg'][2][1] for s in ('near', 'far'))
ref_hip = ref['H'][1]
leg_span = abs(ref_hip - ref['near_leg'][2][1])
for i, (nm, J) in enumerate(zip(names, Js)):
    S, H = J['S'], J['H']
    out = [f'{nm}']
    ks = []
    for sd in ('near', 'far'):
        _, kn, an = J[sd + '_leg'][:3]
        k = angle3(H, kn, an); ks.append(k)
        out.append(f'rodilla {sd} {k:.0f}°')
        if i in (0, 1, 3):
            assert abs(an[1] - AY) < 4e-3, f'{nm}/{sd}: el pie debe quedar apoyado en el suelo'
        if i == 0:
            assert k >= SQUAT_UP_ANGLE_DEG, f'{nm}/{sd}: de pie (rodilla >= {SQUAT_UP_ANGLE_DEG}°)'
            assert tilt(H, an) >= ARM_STANDING_LEG_MIN_TILT_DEG and tilt(S, H) >= ARM_STANDING_TORSO_MIN_TILT_DEG, 'isStandingSideView'
        if i == 1:
            assert k <= SQUAT_DOWN_ANGLE_DEG, f'{nm}/{sd}: abajo (rodilla <= {SQUAT_DOWN_ANGLE_DEG}°)'
        if i == 2:
            assert k >= SQUAT_UP_ANGLE_DEG, f'{nm}/{sd}: en el aire la rodilla se estira (>= {SQUAT_UP_ANGLE_DEG}°) para contar la rep'
        if i == 3:
            assert SQUAT_DOWN_ANGLE_DEG < k < SQUAT_UP_ANGLE_DEG, f'{nm}/{sd}: al aterrizar no debe contar como bajada nueva ni como de pie'
    if i == 2:
        lift = max(ref_ankle - min(J[s + '_leg'][2][1] for s in ('near', 'far')) if False else (J['near_leg'][2][1] - ref['near_leg'][2][1]),
                   J['H'][1] - ref_hip) / leg_span
        assert lift >= JUMPSQUAT_LIFT_FACTOR, f'salto: {lift:.2f} < {JUMPSQUAT_LIFT_FACTOR}'
        out.append(f'salto {lift * 100:.0f}% del largo de pierna (min {JUMPSQUAT_LIFT_FACTOR * 100:.0f}%)')
        assert min(J[s + '_leg'][2][1] for s in ('near', 'far')) > AY + 0.2, 'los pies deben verse despegados del suelo'
    out.append(f'pierna {tilt(H, J["near_leg"][2]):.0f}° tronco {tilt(S, H):.0f}°')
    print(' | '.join(out))
print('OK: la sentadilla con salto coincide con los umbrales del contador (jumpsquat, processSquat)')
