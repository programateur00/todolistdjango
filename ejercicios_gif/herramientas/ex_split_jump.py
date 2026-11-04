"""Split jumps (salto en zancada con cambio de pierna en el aire), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que split-squat / sentadillas-con-salto / tuck-jumps. SIN cara (ni nariz ni ojo ni oreja: cabeza lisa, plain_head=True).
Forma de referencia (Redefining Strength "split squat jumps", Get Healthy U "split jumps", Fitbod/Planfit "lunge jump"): desde una zancada profunda (las dos rodillas
~90°, tronco ERGUIDO, talon de delante en el suelo, rodilla de atras casi en el suelo y talon trasero levantado) se salta explosivamente (los brazos ayudan al impulso),
EN EL AIRE SE CAMBIAN LAS PIERNAS (la de delante va atras y la de atras va delante) y se aterriza amortiguando en zancada con la pierna contraria delante.
Como lo mira la app (workout.js: processSplitJump, bloque SPLITJUMP_*, counter "splitjump", slug split-jump, migracion 0122): de PERFIL, todo en LARGOS DE TRONCO
(hombro->cadera) con el valle -> pico -> valle de la cadera:
  1. ARMAR: en zancada, quieto, tronco erguido (altura hombro->cadera / tronco >= SPLITJUMP_ARM_UPRIGHT_MIN = 0.8) y tobillos separados >= SPLITJUMP_ARM_STRIDE_MIN = 1.0,
  2. DESPEGUE: la cadera sube >= SPLITJUMP_TAKEOFF_RISE = 0.12 sobre el valle,
  3. PICO: la cadera sube >= SPLITJUMP_MIN_RISE = 0.25 y los DOS tobillos suben a la vez >= SPLITJUMP_FEET_OFF_MIN = 0.12 sobre SU suelo (manda el que menos sube),
  4. CAIDA: la cadera recorre de vuelta SPLITJUMP_FALL_FRACTION = 0.55 de lo que subio -> aterrizaje,
  5. ATERRIZAJE EN ZANCADA: tobillos separados >= SPLITJUMP_LAND_STRIDE_MIN = 0.8 y al menos una rodilla <= SPLITJUMP_LAND_KNEE_MAX_DEG = 155 (amortigua). Cuenta 1 repeticion.
GIF de 10 fotogramas (2 saltos = 1 ciclo; el segundo es el espejo del primero, asi que se ve el cambio de pierna en los dos sentidos):
1 ZANCADA ABAJO con la pierna cercana delante (flecha gris arriba) -> 2 DESPEGUE (piernas estiradas, pies despegados, brazos adelante-arriba) -> 3 PUNTO MAS ALTO (las piernas se cruzan
bajo la cadera, flecha gris doble horizontal = «cambio de pierna»; brazos arriba) -> 4 CAIDA (la pierna cercana ya atras y la lejana adelante, listas para aterrizar) -> 5 ATERRIZAJE
amortiguado con la pierna lejana delante (flecha gris abajo) -> 6 zancada abajo (flecha arriba) -> 7 despegue -> 8 punto mas alto -> 9 caida -> 10 aterrizaje con la cercana delante
(flecha abajo) -> (otra vez el 1).
Los pies NO se mueven mientras estan en el suelo (el delantero plano, el trasero apoyado en la punta con el talon levantado); manos delante del pecho en la zancada.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert, aspectos 16:9, 4:3 y 1:1) y se simula la maquina de estados: 1 repeticion por salto.
Uso: python ex_split_jump.py [carpeta_salida] [clave=valor ...]   (genera split-jumps.gif + PNG de cada fotograma; usar una carpeta temporal para probar)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(xf=0.90, xr=-0.90,          # x del tobillo delantero (FIJO mientras esta en el suelo) y de la punta/tobillo trasero con el pie plano; la cadera esta en x = 0
           kneeB=90, kneeL=112,        # angulo de la rodilla delantera abajo / al aterrizar (amortiguando)
           frearB=-35, frearL=-22,     # angulo del pie de atras abajo / al aterrizar (0 = plano; la PUNTA no se mueve y el talon sube)
           torso=90, head=90,          # tronco erguido y cuello neutro, mirada al frente
           clearT=0.08, clearA=0.30, clearR=0.12,   # altura de lo mas bajo de los pies sobre el suelo en el despegue / en el punto mas alto / en la caida
           # despegue: piernas estiradas (la que estaba delante apunta abajo-adelante, la de atras abajo-atras), puntas hacia abajo
           toF=(286, 282, 308), toR=(250, 246, 274),
           # en el aire: la pierna que iba delante se va atras con la rodilla flexionada y la que iba atras viene adelante
           apB=(258, 240, 268), apF=(302, 274, 304),
           # en el punto mas alto: las piernas se cruzan bajo la cadera (la que se va atras / la que viene adelante), rodillas algo flexionadas
           psB=(268, 248, 276), psF=(282, 264, 292),
           # brazos (angulo del brazo, del antebrazo; cercano y lejano): delante del pecho / despegue / en el aire
           chest_n=(285, 75), chest_f=(278, 68), take_n=(28, 45), take_f=(38, 55), air_n=(48, 50), air_f=(58, 62), fall_n=(20, 40), fall_f=(30, 52),
           margin=0.34, arrows=1, arrow_gap=0.55, arrow_len=0.5, sw_len=0.55,
           durB=800, durT=330, durA=500, durF=300, durL=450)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)
CFG = {k: (tuple(v) if isinstance(v, list) else v) for k, v in CFG.items()}

# mismos umbrales que workout.js (SPLITJUMP_*)
SPLITJUMP_ARM_STRIDE_MIN = 1.0
SPLITJUMP_ARM_UPRIGHT_MIN = 0.8
SPLITJUMP_TAKEOFF_RISE = 0.12
SPLITJUMP_MIN_RISE = 0.25
SPLITJUMP_FEET_OFF_MIN = 0.12
SPLITJUMP_FALL_FRACTION = 0.55
SPLITJUMP_LAND_STRIDE_MIN = 0.8
SPLITJUMP_LAND_KNEE_MAX_DEG = 155


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
TOE_R = np.array([CFG['xr'], YF]) + FLAT_TOE     # punta del pie de atras (FIJA mientras esta en el suelo)
TOE_R[1] = 0.04                                  # apoyada en el suelo (punta - 0.04 = 0, como ground_shift)


def toe_ankle(toe, fa):
    """tobillo trasero para un angulo de pie fa con la PUNTA en 'toe' (el talon gira sobre ella)"""
    return np.asarray(toe, float) - foot_geom(np.zeros(2), fa)[1]


def hip_for_knee(dx, target):
    """altura de la cadera para la que la rodilla delantera mide 'target' grados, con el tobillo delantero 'dx' por delante de la cadera"""
    lo, hi = YF + 0.3, YF + L_THIGH + L_SHIN + 0.5
    for _ in range(60):
        m = (lo + hi) / 2; d = np.hypot(dx, m - YF)
        ang_ = np.degrees(np.arccos(np.clip((L_THIGH ** 2 + L_SHIN ** 2 - d * d) / (2 * L_THIGH * L_SHIN), -1, 1)))
        lo, hi = (lo, m) if ang_ > target else (m, hi)
    return (lo + hi) / 2


HB, HL = hip_for_knee(CFG['xf'], CFG['kneeB']), hip_for_knee(CFG['xf'], CFG['kneeL'])
PLAIN = dict(plain_head=True)    # cabeza lisa: sin nariz, ojo ni oreja


def arms(n, f):
    return dict(near_arm=('fk',) + tuple(n), far_arm=('fk',) + tuple(f), near_hand=n[1], far_hand=f[1])


def other(sd):
    return 'far' if sd == 'near' else 'near'


def lunge(front, h, fr, a):
    """zancada con la pierna 'front' delante (pie plano en AF) y la otra detras (punta fija en TOE_R, talon a angulo fr); cadera en x = 0 a altura h"""
    legs = {front: ('ik', tuple(AF), 'ccw', 0), other(front): ('ik', tuple(toe_ankle(TOE_R, fr)), 'ccw', fr)}
    return dict(f=1, ground=False, hip=(0.0, h), torso=CFG['torso'], head=CFG['head'], **PLAIN, near_leg=legs['near'], far_leg=legs['far'], **a)


def air(near_leg, far_leg, clear, a, torso=90):
    """pose en el aire con la cadera puesta para que lo mas bajo de los pies quede 'clear' sobre el suelo"""
    p = dict(f=1, ground=False, hip=(0.0, 0.0), torso=torso, head=torso, **PLAIN, near_leg=near_leg, far_leg=far_leg, **a)
    J = build_side(p)
    low = min(min(J[s + '_leg'][3][1] - 0.04, J[s + '_leg'][4][1] - 0.04, J[s + '_leg'][2][1] - 0.07) for s in ('near', 'far'))
    p['hip'] = (0.0, clear - low)
    return p


def fk(spec):
    # 5o elemento True = empeine SIEMPRE por delante del eje talon->punta (figura.foot_poly consistent): sin esto, un pie en el aire que apunta hacia abajo-atras
    # (pierna que se va atras) dibuja el empeine al reves y queda con un gancho feo
    return ('fk',) + tuple(spec) + (True,)


A_CHEST = arms(CFG['chest_n'], CFG['chest_f'])
A_TAKE = arms(CFG['take_n'], CFG['take_f'])
A_AIR = arms(CFG['air_n'], CFG['air_f'])
A_FALL = arms(CFG['fall_n'], CFG['fall_f'])


def takeoff(front):
    legs = {front: fk(CFG['toF']), other(front): fk(CFG['toR'])}
    return air(legs['near'], legs['far'], CFG['clearT'], A_TAKE)


def peak(front):
    """punto mas alto: las dos piernas bajo la cadera, cruzandose; front = la que iba delante (y se va atras)"""
    legs = {front: fk(CFG['psB']), other(front): fk(CFG['psF'])}
    return air(legs['near'], legs['far'], CFG['clearA'], A_AIR)


def fall(front):
    """caida: front = la que iba delante y ahora esta ATRAS; la otra ya esta delante, lista para aterrizar"""
    legs = {front: fk(CFG['apB']), other(front): fk(CFG['apF'])}
    return air(legs['near'], legs['far'], CFG['clearR'], A_FALL)


# 1 abajo (near delante) / 2 despegue / 3 punto mas alto / 4 caida (near atras) / 5 aterrizaje (far delante) / 6 abajo (far delante) / 7 despegue / 8 punto mas alto / 9 caida (far atras) / 10 aterrizaje (near delante)
frames = [lunge('near', HB, CFG['frearB'], A_CHEST), takeoff('near'), peak('near'), fall('near'), lunge('far', HL, CFG['frearL'], A_CHEST),
          lunge('far', HB, CFG['frearB'], A_CHEST), takeoff('far'), peak('far'), fall('far'), lunge('near', HL, CFG['frearL'], A_CHEST)]
durs = [CFG['durB'], CFG['durT'], CFG['durA'], CFG['durF'], CFG['durL']] * 2
JSs = [build_side(p_) for p_ in frames]     # ground=False: ya estan con el suelo en y = 0

# flecha gris POR DETRAS de la espalda (por detras del pie trasero en el aire), a la altura de los hombros del fotograma; flecha doble horizontal bajo los pies en el aire
AX = min(all_points(J)[:, 0].min() for J in JSs) - CFG['arrow_gap']


def vflecha(J, bajando):
    def f(pen):
        m = J['S'][1]; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


def hflecha(J):
    def f(pen):
        y = min(J[s + '_leg'][4][1] for s in ('near', 'far')) - 0.20
        draw_line_arrow(pen, (-CFG['sw_len'] / 2, y), (CFG['sw_len'] / 2, y), both=True)
    return f


if CFG['arrows']:
    extras = [[vflecha(JSs[0], False)], [vflecha(JSs[1], False)], [hflecha(JSs[2])], [], [vflecha(JSs[4], True)],
              [vflecha(JSs[5], False)], [vflecha(JSs[6], False)], [hflecha(JSs[7])], [], [vflecha(JSs[9], True)]]
else:
    extras = [[] for _ in frames]
bb = (AX - 0.15, 0.0, max(all_points(J)[:, 0].max() for J in JSs) + 0.1, max(J['hd'][1] for J in JSs) + 0.3)
imgs = render_scene(frames, OUT + 'split-jumps', durations=[int(d) for d in durs], margin=CFG['margin'], bbox_extra=bb, extras=extras, ground_all=False)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processSplitJump)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def medidas(J):
    """todo en LARGOS DE TRONCO (hombro->cadera), como la app (que ya corrige el aspecto del video: la geometria es la del dibujo, sin deformar)"""
    H, S = J['H'], J['S']
    torso = float(np.linalg.norm(S - H))
    ank = [J['near_leg'][2], J['far_leg'][2]]
    return dict(hipY=H[1] / torso, ankY=[a[1] / torso for a in ank], stride=abs(ank[0][0] - ank[1][0]) / torso,
                upright=(S[1] - H[1]) / torso,
                knees=[ang3(J[s + '_leg'][0], J[s + '_leg'][1], J[s + '_leg'][2]) for s in ('near', 'far')])


Ms = [medidas(J) for J in JSs]
nombres = ['zancada abajo', 'despegue', 'punto mas alto', 'caida', 'aterrizaje'] * 2
for n_, m in zip(nombres, Ms):
    print(f"{n_:14s}: cadera y {m['hipY']:.2f} | tobillos y {m['ankY'][0]:.2f} / {m['ankY'][1]:.2f} | zancada {m['stride']:.2f} troncos | rodillas {m['knees'][0]:.0f}° / {m['knees'][1]:.0f}° | tronco erguido {m['upright']:.2f}")

for half in (0, 5):
    bot, tk, ar, fl, ld = (Ms[half + i] for i in range(5))
    # --- armar: zancada, tronco erguido
    assert bot['stride'] >= SPLITJUMP_ARM_STRIDE_MIN and bot['upright'] >= SPLITJUMP_ARM_UPRIGHT_MIN, 'armar: zancada >= 1.0 troncos y tronco erguido'
    # --- despegue y pico (valle = zancada abajo)
    assert tk['hipY'] - bot['hipY'] >= SPLITJUMP_TAKEOFF_RISE, f"despegue: cadera +{tk['hipY'] - bot['hipY']:.2f} >= {SPLITJUMP_TAKEOFF_RISE}"
    rise = ar['hipY'] - bot['hipY']
    assert rise >= SPLITJUMP_MIN_RISE + 0.1, f'pico: cadera +{rise:.2f} (>= {SPLITJUMP_MIN_RISE}, con margen)'
    lifts = [ar['ankY'][i] - bot['ankY'][i] for i in range(2)]
    assert min(lifts) >= SPLITJUMP_FEET_OFF_MIN + 0.1, f'pico: los DOS tobillos suben a la vez (+{lifts[0]:.2f} / +{lifts[1]:.2f} >= {SPLITJUMP_FEET_OFF_MIN}, con margen)'
    # --- caida (cadera baja sin parar) y aterrizaje en zancada
    assert ar['hipY'] > fl['hipY'] > ld['hipY'], 'la cadera baja del punto mas alto a la caida y al aterrizaje'
    fall_ = (ar['hipY'] - ld['hipY']) / rise
    assert fall_ >= SPLITJUMP_FALL_FRACTION, f'caida: la cadera recorre {fall_:.2f} de lo subido (>= {SPLITJUMP_FALL_FRACTION})'
    assert ld['stride'] >= SPLITJUMP_LAND_STRIDE_MIN and min(ld['knees']) <= SPLITJUMP_LAND_KNEE_MAX_DEG - 20, 'aterrizaje: zancada y rodilla flexionada'
    print(f'  salto {half // 5 + 1}: cadera +{rise:.2f} (mín {SPLITJUMP_MIN_RISE}) | pies +{min(lifts):.2f} (mín {SPLITJUMP_FEET_OFF_MIN}) | caída {fall_ * 100:.0f}% (mín {SPLITJUMP_FALL_FRACTION * 100:.0f}%) | aterrizaje zancada {ld["stride"]:.2f} rodilla {min(ld["knees"]):.0f}°')

# --- forma
for i in (0, 4, 5, 9):                         # en el suelo: los pies tocan el suelo, huesos con su largo, delantero plano y fijo, rodilla delantera sin pasar de la punta
    J = JSs[i]
    for sd in ('near', 'far'):
        hp, kn, an, he, to = J[sd + '_leg']
        assert abs(min(he[1] - 0.04, to[1] - 0.04, an[1] - 0.07)) < 3e-3, f'fotograma {i + 1}: los pies deben tocar el suelo'
        assert abs(np.linalg.norm(kn - hp) - L_THIGH) < 1e-6 and abs(np.linalg.norm(an - kn) - L_SHIN) < 1e-6, f'fotograma {i + 1}: huesos con su largo'
    fr_ = 'near' if i in (0, 9) else 'far'
    rr_ = other(fr_)
    assert abs(J[fr_ + '_leg'][2][0] - CFG['xf']) < 2e-3 and abs(J[fr_ + '_leg'][3][1] - J[fr_ + '_leg'][4][1]) < 0.03, f'fotograma {i + 1}: pie delantero plano y fijo'
    assert J[fr_ + '_leg'][1][0] <= J[fr_ + '_leg'][4][0] + 0.02, f'fotograma {i + 1}: la rodilla delantera no pasa de la punta del pie'
    assert np.allclose(J[rr_ + '_leg'][4], TOE_R, atol=2e-3), f'fotograma {i + 1}: la punta del pie de atras no se mueve'
    assert abs(ang(J['S'] - J['H']) - 90) < 1e-6, f'fotograma {i + 1}: tronco erguido'
JB = JSs[0]
assert JB['far_leg'][1][1] <= 0.33, 'abajo: la rodilla de atras queda a un palmo del suelo'
assert JB['far_leg'][3][1] > JB['far_leg'][4][1] + 0.12, 'abajo: talon de atras levantado, apoyado en la punta'
assert abs(JB['near_leg'][1][1] - JB['H'][1]) < 0.12, 'abajo: muslo delantero paralelo al suelo'
assert abs(ang(JB['near_leg'][2] - JB['near_leg'][1]) + 90) < 22, 'abajo: la espinilla delantera casi vertical'
for i in (1, 2, 3, 6, 7, 8):                   # en el aire: los dos pies despegados
    J = JSs[i]
    assert min(min(J[s + '_leg'][3][1], J[s + '_leg'][4][1], J[s + '_leg'][2][1]) for s in ('near', 'far')) > 0.05, f'fotograma {i + 1}: los dos pies despegados del suelo'
# --- cambio de pierna: antes de saltar delante la cercana (1), tras la caida ya esta detras (4) y se aterriza con la lejana delante (5); y al reves en la segunda mitad
for i, (a_, b_) in ((0, ('near', 'far')), (3, ('far', 'near')), (4, ('far', 'near')), (5, ('far', 'near')), (8, ('near', 'far')), (9, ('near', 'far'))):
    assert JSs[i][a_ + '_leg'][2][0] > JSs[i][b_ + '_leg'][2][0], f'fotograma {i + 1}: la pierna {a_} va delante de la {b_}'
print('OK: split jumps coincide con los umbrales del contador (splitjump, processSplitJump)')
