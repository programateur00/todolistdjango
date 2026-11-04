"""Switchblade jumps (salto en tijera tocandose el pie de delante), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que tuck-jumps / sentadillas-con-salto / burpees. SIN cara (ni nariz ni ojo ni oreja): cabeza ovalada lisa (plain_head=True).
Forma de referencia (tutoriales de calistenia «Switchblade jump»): de pie con los pies juntos -> pequeño impulso (media sentadilla, brazos atras) -> saltar ->
en el aire las piernas se abren en TIJERA, ESTIRADAS, una hacia delante y otra hacia atras (como una navaja que se abre), el tronco se pliega hacia delante
y la mano baja a TOCAR EL PIE DE DELANTE -> cerrar las piernas y aterrizar suave con los pies juntos. La siguiente repeticion alterna la pierna.
Como lo mira la app (workout.js: counter "switchblade", SWITCHBLADE_*): de PERFIL, todo normalizado con el LARGO DE PIERNA medido de pie:
  1. SALTO: la cadera sube >= SWITCHBLADE_MIN_HIP_RISE = 0.08 largos de pierna sobre su altura de pie,
  2. TIJERA: separacion HORIZONTAL entre los dos tobillos >= SWITCHBLADE_MIN_SPLIT = 0.80 largos de pierna,
  3. PIERNAS ESTIRADAS: las dos rodillas >= SWITCHBLADE_SPLIT_KNEE_MIN_DEG = 130° en la maxima separacion,
  4. TOQUE: una muñeca a <= SWITCHBLADE_MAX_HAND_FOOT = 0.40 largos de pierna de un tobillo.
  (armar: de pie, piernas estiradas, rodilla >= SWITCHBLADE_ARM_KNEE_MIN_DEG = 150 y pies a <= SWITCHBLADE_ARM_FEET_MAX_GAP = 0.45 largos de pierna uno del otro.)
GIF de 5 fotogramas: de pie (flecha abajo) -> abajo (media sentadilla, brazos atras, flecha arriba) -> DESPEGUE (cuerpo estirado, pies juntos despegados,
flecha arriba) -> TIJERA en el punto mas alto (pierna de delante estirada, la de atras estirada, tronco plegado, mano en el pie de delante) -> aterrizaje
amortiguado con los pies juntos (flecha abajo) -> vuelve a «de pie» (bucle).
Los pies (planos) NO se mueven mientras estan en el suelo. Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_switchblade.py [carpeta_salida] [clave=valor ...]   (genera switchblade-jumps.gif + PNG de cada fotograma; usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(kU=168, kB=104, kL=124, leanU=2, leanB=16, leanL=12, tU=88, tB=62, tL=70, headd=8, far_dx=-0.10,
           lift=0.30, jump=0.60, air_t=88,
           sp_t=46, sp_head=22,                                   # tijera: inclinacion del tronco sobre la horizontal (90 = erguido) y cabeza respecto al tronco
           fr_th=8, fr_sh=8, fr_ft=40,                        # pierna de DELANTE (la cercana): muslo / espinilla / pie (grados matematicos, 0 = delante, 90 = arriba)
           bk_th=228, bk_sh=225, bk_ft=238,                       # pierna de ATRAS (la lejana)
           tc_dx=-0.18, tc_dy=0.02, fa_ua=150, fa_fa=165,         # brazo lejano: abierto hacia atras/arriba para el equilibrio
                                         # donde cae la muñeca cercana respecto al tobillo delantero (sobre el empeine)
           air_ua=62, air_fa=58, air_far=3, arrows=1, arrow_dx=1.25, arrow_len=0.5, margin=0.40,
           dur0=1000, dur1=800, dur2=500, dur3=1100, dur4=900)
# kU/kB/kL: angulo de la rodilla (cadera-rodilla-tobillo) de pie / abajo / al aterrizar (la app: >=150 para armar)
# leanU/leanB/leanL: inclinacion de la espinilla hacia delante respecto a la vertical; tU/tB/tL: inclinacion del tronco sobre la horizontal (90 = erguido)
# lift: altura de la cadera en el despegue; jump: altura de la cadera en el punto mas alto (unidades = troncos); headd: grados de la cabeza sobre el tronco
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (SWITCHBLADE_*)
SWITCHBLADE_ARM_KNEE_MIN_DEG = 150
SWITCHBLADE_ARM_FEET_MAX_GAP = 0.45
SWITCHBLADE_MIN_HIP_RISE = 0.08
SWITCHBLADE_MIN_SPLIT = 0.80
SWITCHBLADE_SPLIT_KNEE_MIN_DEG = 130
SWITCHBLADE_MAX_HAND_FOOT = 0.40
SWITCHBLADE_LAND_RISE = 0.035

AY = 0.14                        # altura del tobillo con el pie plano apoyado (la suela queda en y=0)
FOOT_FLAT = 0                    # pie plano: la puntera apunta hacia delante (derecha)
PLAIN = dict(plain_head=True)    # cabeza lisa: sin nariz, ojo ni oreja


def squat_geom(K, lean):
    """cadera, rodilla y tobillo (cercano) con el pie plano en (0, AY), la espinilla inclinada 'lean' grados hacia delante y rodilla de K grados"""
    A = np.array([0.0, AY])
    knee = A + L_SHIN * np.array([np.sin(np.deg2rad(lean)), np.cos(np.deg2rad(lean))])
    hip = knee + L_THIGH * dv(270 - lean - K)
    return hip, knee, A


def arms(un, fn, uf, ff):
    return dict(near_arm=('fk', un, fn), far_arm=('fk', uf, ff), near_hand=fn, far_hand=ff)


def pose_floor(K, lean, t, a):
    hip, knee, A = squat_geom(K, lean)
    p = dict(f=1, ground=False, hip=tuple(hip), torso=t, head=t + CFG['headd'], **PLAIN)
    p.update(near_leg=('ik', (0.0, AY), 'ccw', FOOT_FLAT), far_leg=('ik', (CFG['far_dx'], AY), 'ccw', FOOT_FLAT))
    p.update(a)
    return p


# 1) DE PIE: pies juntos, brazos colgando un poco por delante del cuerpo
A_U = arms(268, 282, 262, 276)
# 2) ABAJO: media sentadilla, brazos hacia atras para tomar impulso
A_B = arms(226, 216, 232, 222)
# 5) ATERRIZAJE: pies juntos, amortigua con las rodillas flexionadas y los brazos hacia delante
A_L = arms(312, 343, 306, 337)
FU = pose_floor(CFG['kU'], CFG['leanU'], CFG['tU'], A_U)
FB = pose_floor(CFG['kB'], CFG['leanB'], CFG['tB'], A_B)
FL = pose_floor(CFG['kL'], CFG['leanL'], CFG['tL'], A_L)

hipU = np.array(FU['hip'])
TA = CFG['air_t']
# 3) DESPEGUE: cuerpo estirado y erguido, brazos arriba, pies juntos recien despegados con las puntas hacia abajo
FT = dict(f=1, ground=False, hip=tuple(hipU + np.array([0.0, CFG['lift']])), torso=TA, head=TA + 2, **PLAIN,
          near_leg=('fk', 268, 266, 284), far_leg=('fk', 268 + CFG['air_far'] + 1, 266 + CFG['air_far'], 280),
          **arms(CFG['air_ua'], CFG['air_fa'], CFG['air_ua'] + 10 + CFG['air_far'], CFG['air_fa'] + 12 + CFG['air_far']))

# 4) TIJERA en el punto mas alto: pierna cercana estirada DELANTE (casi horizontal), la lejana estirada ATRAS, tronco plegado hacia delante,
#    las dos manos bajan al pie de delante (la cercana lo toca)
hipK = hipU + np.array([0.0, CFG['jump']])
ankF = hipK + L_THIGH * dv(CFG['fr_th']) + L_SHIN * dv(CFG['fr_sh'])        # tobillo de la pierna de delante
tgtN = ankF + np.array([CFG['tc_dx'], CFG['tc_dy']])                          # muñeca cercana: sobre el empeine
FK = dict(f=1, ground=False, hip=tuple(hipK), torso=CFG['sp_t'], head=CFG['sp_t'] + CFG['sp_head'], **PLAIN,
          near_leg=('fk', CFG['fr_th'], CFG['fr_sh'], CFG['fr_ft']), far_leg=('fk', CFG['bk_th'], CFG['bk_sh'], CFG['bk_ft']),
          near_arm=('ik', tuple(tgtN), 'cw'), far_arm=('fk', CFG['fa_ua'], CFG['fa_fa']), near_hand=355, far_hand=CFG['fa_fa'])
FRAMES = [FU, FB, FT, FK, FL]


def flechas(i):
    if not CFG['arrows']:
        return None
    x = CFG['arrow_dx']; L = CFG['arrow_len']
    if i == 0:   # a punto de bajar
        return [lambda pen: draw_line_arrow(pen, (x, 1.55), (x, 1.55 - L))]
    if i == 1:   # impulso hacia arriba
        return [lambda pen: draw_line_arrow(pen, (x, 0.80), (x, 0.80 + L))]
    if i == 2:   # subiendo
        y = 1.45 + CFG['lift'] * 0.6
        return [lambda pen: draw_line_arrow(pen, (x, y), (x, y + L))]
    if i == 3:   # las piernas se abren: flecha doble horizontal bajo la tijera (de la pierna de atras a la de delante)
        ankB = hipK + L_THIGH * dv(CFG['bk_th']) + L_SHIN * dv(CFG['bk_sh'])      # tobillo de la pierna de atras
        yb = float(ankB[1]) - 0.50
        xa, xb = float(ankB[0]), float(ankF[0])
        return [lambda pen: draw_line_arrow(pen, (xa, yb), (xb, yb), both=True)]
    return [lambda pen: draw_line_arrow(pen, (x, 1.35), (x, 1.35 - L))]


durs = [int(CFG['dur%d' % i]) for i in range(5)]
render_scene(FRAMES, OUT + 'switchblade-jumps', durations=durs, margin=CFG['margin'], extras=[flechas(i) for i in range(5)])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processSwitchblade)
def angle3(a, b, c):
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


Js = [build_side(fr) for fr in FRAMES]
names = ('de pie', 'abajo', 'despegue', 'tijera', 'aterrizaje')
ref = Js[0]
ref_hip = ref['H'][1]
leg_span = ref_hip - ref['near_leg'][2][1]                     # largo de pierna (vertical cadera->tobillo) de pie
for i, (nm, J) in enumerate(zip(names, Js)):
    S, H = J['S'], J['H']
    out = [nm]
    for sd in ('near', 'far'):
        _, kn, an = J[sd + '_leg'][:3]
        k = angle3(H, kn, an)
        out.append(f'rodilla {sd} {k:.0f}°')
        if i in (0, 1, 4):
            assert abs(an[1] - AY) < 4e-3, f'{nm}/{sd}: el pie debe quedar apoyado en el suelo'
        if i == 0:
            assert k >= SWITCHBLADE_ARM_KNEE_MIN_DEG, f'{nm}/{sd}: de pie con las piernas estiradas (>= {SWITCHBLADE_ARM_KNEE_MIN_DEG}°)'
        if i == 3:
            assert k >= SWITCHBLADE_SPLIT_KNEE_MIN_DEG, f'tijera/{sd}: rodilla {k:.0f}° < {SWITCHBLADE_SPLIT_KNEE_MIN_DEG}° (piernas estiradas)'
        if i == 4:
            assert k < 160, f'{nm}/{sd}: al aterrizar las rodillas van flexionadas'
    rise = (H[1] - ref_hip) / leg_span
    out.append(f'cadera {rise * 100:+.0f}% del largo de pierna')
    if i in (0, 1, 4):
        gap = abs(J['near_leg'][2][0] - J['far_leg'][2][0]) / leg_span
        assert gap <= SWITCHBLADE_ARM_FEET_MAX_GAP, f'{nm}: pies separados {gap:.2f} > {SWITCHBLADE_ARM_FEET_MAX_GAP}'
    if i == 2:
        assert rise >= SWITCHBLADE_MIN_HIP_RISE, f'despegue: ya sube {rise:.2f}'
        assert min(J[s + '_leg'][2][1] for s in ('near', 'far')) > AY + 0.1, 'los pies deben verse despegados'
    if i == 3:
        assert rise >= SWITCHBLADE_MIN_HIP_RISE, f'salto: {rise:.2f} < {SWITCHBLADE_MIN_HIP_RISE}'
        assert min(J[s + '_leg'][2][1] for s in ('near', 'far')) > AY + 0.5, 'los pies deben verse bien despegados'
        split = abs(J['near_leg'][2][0] - J['far_leg'][2][0]) / leg_span
        assert split >= SWITCHBLADE_MIN_SPLIT, f'tijera corta: {split:.2f} < {SWITCHBLADE_MIN_SPLIT}'
        assert J['near_leg'][2][0] > J['far_leg'][2][0], 'la pierna cercana va DELANTE (derecha)'
        reach = min(np.linalg.norm(J[a + '_arm'][2] - J[l + '_leg'][2]) for a in ('near', 'far') for l in ('near', 'far')) / leg_span
        assert reach <= SWITCHBLADE_MAX_HAND_FOOT, f'toque: mano-pie {reach:.2f} > {SWITCHBLADE_MAX_HAND_FOOT}'
        out.append(f'tijera {split:.2f} (mín {SWITCHBLADE_MIN_SPLIT}) mano-pie {reach:.2f} (máx {SWITCHBLADE_MAX_HAND_FOOT})')
    if i == 4:
        assert rise <= SWITCHBLADE_LAND_RISE, f'aterrizaje: la cadera sigue +{rise:.2f}'
        out.append(f'cadera {rise * 100:+.0f}% (aterrizado si <= {SWITCHBLADE_LAND_RISE * 100:.1f}%)')
    print(' | '.join(out))
print('OK: el switchblade jump coincide con los umbrales del contador (switchblade)')
