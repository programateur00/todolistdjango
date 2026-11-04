"""Tuck jumps (salto con las rodillas al pecho), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que sentadillas-con-salto / burpees. SIN cara (ni nariz ni ojo ni oreja): cabeza ovalada lisa (plain_head=True).
Forma de referencia (NASM / World Rugby tuck jump test): de pie, pies a la anchura de caderas -> bajar un poco -> saltar lo mas alto posible ->
en el punto mas alto TIRAR DE LAS DOS RODILLAS A LA VEZ HACIA EL PECHO (muslos al menos paralelos al suelo, espinillas colgando, brazos
adelante a la altura de la cintura como «diana» para las rodillas), tronco ERGUIDO -> estirar de nuevo y aterrizar suave con las rodillas flexionadas.
Como lo mira la app (workout.js: counter "tuckjump", TUCKJUMP_*): de frente o de perfil, todo en VERTICAL y normalizado con las medidas de pie:
  1. SALTO: la cadera sube >= TUCKJUMP_MIN_HIP_RISE = 0.12 largos de pierna (cadera->tobillo) sobre su altura de pie,
  2. RODILLAS AL PECHO: la rodilla MAS BAJA llega a >= TUCKJUMP_KNEE_MIN_RISE = -0.10 (largos de muslo respecto a la cadera; 0 = muslo paralelo),
  3. TRONCO ERGUIDO: altura hombro->cadera en el pico >= TUCKJUMP_TORSO_MIN_RATIO = 0.70 de la de pie,
  4. aterrizaje amortiguado (AVISO): la cadera se hunde >= TUCKJUMP_LAND_DIP_MIN = 0.02 largos de pierna bajo su altura de pie.
  (armar: de pie con las piernas estiradas, rodilla >= TUCKJUMP_ARM_KNEE_MIN_DEG = 150.)
GIF de 5 fotogramas: de pie (flecha abajo) -> abajo (media sentadilla, brazos atras, flecha arriba) -> DESPEGUE (cuerpo estirado, pies despegados,
flecha arriba) -> TUCK en el punto mas alto (rodillas al pecho, brazos adelante) -> aterrizaje amortiguado (flecha abajo) -> vuelve a «de pie» (bucle).
Los pies (planos) NO se mueven mientras estan en el suelo. Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_tuck_jump.py [carpeta_salida] [clave=valor ...]   (genera tuck-jumps.gif + PNG de cada fotograma; usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(kU=168, kB=104, kL=124, leanU=2, leanB=16, leanL=12, tU=88, tB=62, tL=70, headd=8, far_dx=-0.10,
           lift=0.30, jump=0.70, air_t=88, tuck_t=86,
           th_n=36, th_f=28, sh_n=258, sh_f=252, ft_n=305, ft_f=300,      # tuck: angulo del muslo / espinilla / pie (cercano y lejano)
           tk_ua=338, tk_fa=2, air_ua=62, air_fa=58, air_far=3, arrows=1, arrow_dx=1.25, arrow_len=0.5, margin=0.40,
           dur0=1000, dur1=800, dur2=500, dur3=1100, dur4=900)
# kU/kB/kL: angulo de la rodilla (cadera-rodilla-tobillo) de pie / abajo / al aterrizar (la app: >=150 para armar)
# leanU/leanB/leanL: inclinacion de la espinilla hacia delante respecto a la vertical; tU/tB/tL: inclinacion del tronco sobre la horizontal (90 = erguido)
# lift: altura de la cadera en el despegue; jump: altura de la cadera en el punto mas alto (unidades = troncos); headd: grados de la cabeza sobre el tronco
# tk_ua/tk_fa: brazo y antebrazo en el tuck (adelante, a la altura del pecho/cintura, como diana para las rodillas)
# th_*/sh_*/ft_*: angulos matematicos (0 = delante, 90 = arriba) del muslo, espinilla y pie en el tuck; far_dx: cuanto queda el pie lejano por detras
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (TUCKJUMP_*)
TUCKJUMP_ARM_KNEE_MIN_DEG = 150
TUCKJUMP_MIN_HIP_RISE = 0.12
TUCKJUMP_KNEE_MIN_RISE = -0.10
TUCKJUMP_TORSO_MIN_RATIO = 0.70
TUCKJUMP_LAND_DIP_MIN = 0.02

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


# 1) DE PIE: brazos colgando un poco por delante del cuerpo
A_U = arms(268, 282, 262, 276)
# 2) ABAJO: media sentadilla, brazos hacia atras para tomar impulso
A_B = arms(226, 216, 232, 222)
# 5) ATERRIZAJE: amortigua con las rodillas flexionadas y los brazos hacia delante
A_L = arms(312, 343, 306, 337)
FU = pose_floor(CFG['kU'], CFG['leanU'], CFG['tU'], A_U)
FB = pose_floor(CFG['kB'], CFG['leanB'], CFG['tB'], A_B)
FL = pose_floor(CFG['kL'], CFG['leanL'], CFG['tL'], A_L)

hipU = np.array(FU['hip'])
TA = CFG['air_t']
# 3) DESPEGUE: cuerpo estirado y erguido, brazos arriba, pies recien despegados con las puntas hacia abajo
FT = dict(f=1, ground=False, hip=tuple(hipU + np.array([0.0, CFG['lift']])), torso=TA, head=TA + 2, **PLAIN,
          near_leg=('fk', 268, 266, 284), far_leg=('fk', 268 + CFG['air_far'] + 1, 266 + CFG['air_far'], 280),
          **arms(CFG['air_ua'], CFG['air_fa'], CFG['air_ua'] + 10 + CFG['air_far'], CFG['air_fa'] + 12 + CFG['air_far']))
# 4) TUCK en el punto mas alto: las dos rodillas al pecho (muslos por encima de la horizontal), espinillas colgando, tronco erguido, brazos adelante abajo
FK = dict(f=1, ground=False, hip=tuple(hipU + np.array([0.0, CFG['jump']])), torso=CFG['tuck_t'], head=CFG['tuck_t'] + 4, **PLAIN,
          near_leg=('fk', CFG['th_n'], CFG['sh_n'], CFG['ft_n']), far_leg=('fk', CFG['th_f'], CFG['sh_f'], CFG['ft_f']),
          **arms(CFG['tk_ua'], CFG['tk_fa'], CFG['tk_ua'] - 6, CFG['tk_fa'] - 6))
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
    if i == 3:   # las rodillas suben hacia el pecho
        y = hipU[1] + CFG['jump'] - 0.15
        return [lambda pen: draw_line_arrow(pen, (x + 0.35, y), (x + 0.35, y + L))]
    return [lambda pen: draw_line_arrow(pen, (x, 1.35), (x, 1.35 - L))]


durs = [int(CFG['dur%d' % i]) for i in range(5)]
render_scene(FRAMES, OUT + 'tuck-jumps', durations=durs, margin=CFG['margin'], extras=[flechas(i) for i in range(5)])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processTuckJump)
def angle3(a, b, c):
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


Js = [build_side(fr) for fr in FRAMES]
names = ('de pie', 'abajo', 'despegue', 'tuck', 'aterrizaje')
ref = Js[0]
ref_hip = ref['H'][1]
leg_span = ref_hip - ref['near_leg'][2][1]                     # largo de pierna (vertical cadera->tobillo) de pie
ref_thigh = ref_hip - ref['near_leg'][1][1]                    # largo de muslo (vertical cadera->rodilla) de pie
ref_torso = ref['S'][1] - ref['H'][1]                          # altura hombro->cadera de pie
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
            assert k >= TUCKJUMP_ARM_KNEE_MIN_DEG, f'{nm}/{sd}: de pie con las piernas estiradas (>= {TUCKJUMP_ARM_KNEE_MIN_DEG}°)'
        if i == 4:
            assert k < 160, f'{nm}/{sd}: al aterrizar las rodillas van flexionadas'
    rise = (H[1] - ref_hip) / leg_span
    torso = (S[1] - H[1]) / ref_torso
    out.append(f'cadera {rise * 100:+.0f}% del largo de pierna')
    if i == 2:
        assert rise >= TUCKJUMP_MIN_HIP_RISE, f'despegue: ya sube {rise:.2f}'
        assert min(J[s + '_leg'][2][1] for s in ('near', 'far')) > AY + 0.1, 'los pies deben verse despegados'
    if i == 3:
        assert rise >= TUCKJUMP_MIN_HIP_RISE, f'salto: {rise:.2f} < {TUCKJUMP_MIN_HIP_RISE}'
        kr = [(J[s + '_leg'][1][1] - H[1]) / ref_thigh for s in ('near', 'far')]
        assert min(kr) >= TUCKJUMP_KNEE_MIN_RISE, f'rodillas bajas: {kr}'
        assert torso >= TUCKJUMP_TORSO_MIN_RATIO, f'tronco inclinado: {torso:.2f}'
        assert min(J[s + '_leg'][2][1] for s in ('near', 'far')) > AY + 0.5, 'los pies deben verse bien despegados'
        out.append(f'rodillas {kr[0]:.2f}/{kr[1]:.2f} (mín {TUCKJUMP_KNEE_MIN_RISE}) tronco {torso:.2f} (mín {TUCKJUMP_TORSO_MIN_RATIO})')
    if i == 4:
        assert -rise >= TUCKJUMP_LAND_DIP_MIN, f'aterrizaje rigido: hundimiento {-rise:.2f}'
        out.append(f'hundimiento {-rise * 100:.0f}% (mín {TUCKJUMP_LAND_DIP_MIN * 100:.0f}%)')
    print(' | '.join(out))
print('OK: el tuck jump coincide con los umbrales del contador (tuckjump)')
