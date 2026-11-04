"""Burpees, vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones / sentadillas-con-salto / plancha-dinamica.
SIN cara (ni nariz ni ojo ni oreja): cabeza ovalada lisa (plain_head=True) y no se usa cara().

Forma (la de siempre): DE PIE -> agacharse y poner las manos en el suelo -> tirar los pies atras de un salto hasta la plancha ->
flexion (bajar el pecho y subir) -> volver a saltar con los pies hacia las manos -> saltar hacia arriba con los brazos por encima de la cabeza.
Las manos NO se mueven mientras estan en el suelo; los pies vuelven al mismo sitio donde estaban de pie.

Como lo mira la app (workout.js: processBurpee, BURPEE_*, counter "burpee", slug burpee, migracion 0076): de PERFIL, con hombro, codo, muñeca,
cadera, rodilla y tobillo del lado mejor visto. Maquina de estados: top (de pie) -> down (rodilla <= 140) -> plank (tronco <= 40° sobre la
horizontal, hombro-cadera-tobillo >= 135 y codo >= 140) -> pushdown (codo <= 110) -> plank (codo >= 135) -> up (tronco >= 45°) -> de pie
(rodilla >= 160 y tronco >= 55°) = 1 repeticion.
GIF de 7 fotogramas: de pie (flecha abajo) -> agachado con las manos en el suelo (flecha: los pies saldran hacia atras) -> pies EN EL AIRE hacia atras
(flecha hacia atras) -> plancha (flecha abajo) -> flexion abajo (flecha arriba) -> pies de vuelta junto a las manos, agachado (flecha arriba) ->
salto con los brazos por encima de la cabeza (flecha arriba) -> (bucle).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert) y se simula la maquina de estados: 1 vuelta = 1 repeticion.
Uso: python ex_burpee.py [carpeta_salida] [clave=valor ...]   (genera burpees.gif + PNG de cada fotograma; usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, elbB=64, far_dx=-0.07, foot=292, footF=296, far_t=1.5, headd=9, fingers=1,
           dfoot=0.95,                                   # distancia manos -> pies cuando estan agachado (x de la mano - x del tobillo)
           sqH=1.00, sqT=13, sqElb=165, sqHead=18,       # agachado: altura de la cadera, inclinacion del tronco, codo y cabeza sobre el tronco
           kickT=13, kickPike=-10, kickElb=172, kickHead=14,   # pies en el aire atras: inclinacion del tronco, grados de pique en la cadera, codo, cabeza
           jump=0.46, air_t=89, air_ua=62, air_fa=58, air_far=3,
           arrows=1, arrow_len=0.5, margin=0.30,
           dur1=900, dur2=700, dur3=350, dur4=600, dur5=800, dur6=600, dur7=650, left=0.30)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (BURPEE_*)
STAND_KNEE_MIN = 160
STAND_TILT_MIN = 55
DOWN_KNEE_MAX = 140
PLANK_MAX_TILT = 40
PLANK_LINE_MIN = 135
PLANK_ARM_MIN = 140
PUSHUP_DOWN = 110
PUSHUP_UP = 135
RETURN_TILT_MIN = 45

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo
AY = 0.14                       # altura del tobillo con el pie plano apoyado (la suela queda en y=0)
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo
PLAIN = dict(plain_head=True)   # cabeza lisa: sin nariz, ojo ni oreja


def elbow_len(deg):
    """distancia hombro-muñeca para un angulo de codo dado"""
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


# ------------------------------------------------------------------------------ plancha: el cuerpo recto gira alrededor de las puntas de los pies
def pose_t(t, hip):
    f1 = dict(f=1, ground=False, hip=hip, torso=t, head=t + CFG['headd'], **PLAIN)
    legs = dict(near_leg=('fk', 180 + t, 180 + t, CFG['foot']),
                far_leg=('fk', 180 + t + CFG['far_t'], 180 + t + CFG['far_t'], CFG['footF']))
    return dict(f1, **legs, near_arm=('fk', 270, 0), far_arm=('fk', 270, 0))


def feet_low(J):
    lows = []
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        lows += [k[1] - 0.13, he[1] - 0.04, to[1] - 0.04, a[1] - 0.07]
    return min(lows)


def toe_x(J):
    return min(J[s + '_leg'][4][0] for s in ('near', 'far'))


_T = np.linspace(2, 50, 4801)
_S = []
for _t in _T:
    _J = build_side(pose_t(_t, (0.0, 0.0)))
    _dy = -feet_low(_J); _dx = 0.0 - toe_x(_J)
    _S.append((_J['S'] + np.array([_dx, _dy]), (_dx, _dy)))

shA = WY + elbow_len(CFG['elbA'])
iA = min(range(len(_T)), key=lambda i: abs(_S[i][0][1] - shA))
assert abs(_S[iA][0][1] - shA) < 2e-3, 'no hay solucion de postura en la plancha'
tA, hipA = float(_T[iA]), _S[iA][1]
HX = float(_S[iA][0][0])                       # x de las manos (FIJAS en todo el ejercicio)
HXF = HX + CFG['far_dx']


def solve_elbow(elb):
    d = elbow_len(elb)
    cand = [i for i in range(len(_T)) if WY + 0.2 < _S[i][0][1] <= shA + 1e-6]
    i = min(cand, key=lambda i: abs(np.hypot(_S[i][0][0] - HX, _S[i][0][1] - WY) - d))
    assert abs(np.hypot(_S[i][0][0] - HX, _S[i][0][1] - WY) - d) < 4e-3, 'no hay solucion de postura para el codo %s' % elb
    return float(_T[i]), _S[i][1]


tB, hipB = solve_elbow(CFG['elbB'])


def plank_pose(t, hip):
    p = pose_t(t, hip)
    p['near_arm'] = ('ik', (HX, WY), 'cw'); p['far_arm'] = ('ik', (HXF, WY), 'cw')
    p['near_hand'] = HAND; p['far_hand'] = HAND
    return p


F_PLANK = plank_pose(tA, hipA)
F_DOWN = plank_pose(tB, hipB)

# ------------------------------------------------------------------------------ de pie / agachado / pies en el aire / salto
XA = HX - CFG['dfoot']                         # x de los pies cuando estan cerca de las manos (los mismos que de pie)
XAF = XA - 0.10                                # pie lejano algo mas atras para que se vean los dos


def reach_pose(hy, t, elb, headd, ank_y, ank_dx, foot):
    """cadera a altura hy y tronco a t grados; la x de la cadera sale de que las manos esten en (HX, WY) con el codo a 'elb' grados"""
    d = elbow_len(elb)
    sy = hy + np.sin(np.deg2rad(t))
    drop = sy - WY
    assert drop < d, f'el hombro queda demasiado alto para llegar al suelo ({drop:.2f} > {d:.2f}); baja la cadera o inclina el tronco'
    sx = HX - np.sqrt(d * d - drop * drop)
    hx = sx - np.cos(np.deg2rad(t))
    return dict(f=1, ground=False, hip=(hx, hy), torso=t, head=t + headd, **PLAIN,
                near_leg=('ik', (XA + ank_dx, ank_y), 'ccw', foot), far_leg=('ik', (XAF + ank_dx, ank_y), 'ccw', foot),
                near_arm=('ik', (HX, WY), 'ccw'), far_arm=('ik', (HXF, WY), 'ccw'), near_hand=HAND, far_hand=HAND)


F_SQUAT = reach_pose(CFG['sqH'], CFG['sqT'], CFG['sqElb'], CFG['sqHead'], AY, 0.0, 0)

# pies EN EL AIRE (se acaban de lanzar hacia atras): manos fijas y brazos estirados (el hombro queda donde en la plancha), cuerpo casi recto
# pero con la cadera un poco mas alta que los pies (pique), piernas estiradas hacia atras y puntas hacia abajo
_SA = np.array(_S[iA][0])                                    # hombro en la plancha (brazos casi rectos)
_tk = CFG['kickT']
F_KICK = dict(f=1, ground=False, hip=tuple(_SA - dv(_tk)), torso=_tk, head=_tk + CFG['kickHead'], **PLAIN,
              near_leg=('fk', 180 + _tk + CFG['kickPike'], 180 + _tk + CFG['kickPike'], 288),
              far_leg=('fk', 180 + _tk + CFG['kickPike'] + CFG['far_t'], 180 + _tk + CFG['kickPike'] + CFG['far_t'], 292),
              near_arm=('ik', (HX, WY), 'cw'), far_arm=('ik', (HXF, WY), 'cw'), near_hand=HAND, far_hand=HAND)

LEG = L_THIGH + L_SHIN
F_STAND = dict(f=1, ground=False, hip=(XA, AY + LEG - 0.015), torso=90, head=92, **PLAIN,
               near_leg=('ik', (XA, AY), 'ccw', 0), far_leg=('ik', (XAF, AY), 'ccw', 0),
               near_arm=('fk', 268, 282), far_arm=('fk', 262, 276), near_hand=282, far_hand=276)

hipJ = np.array([XA, AY + LEG - 0.015 + CFG['jump']])
TA = CFG['air_t']; af = CFG['air_far']
F_JUMP = dict(f=1, ground=False, hip=tuple(hipJ), torso=TA, head=TA + 2, **PLAIN,
              near_leg=('fk', 268, 266, 284), far_leg=('fk', 268 + af + 1, 266 + af, 280),
              near_arm=('fk', CFG['air_ua'], CFG['air_fa']), far_arm=('fk', CFG['air_ua'] + 10 + af, CFG['air_fa'] + 12 + af),
              near_hand=CFG['air_fa'], far_hand=CFG['air_fa'] + 12 + af)

FRAMES = [F_STAND, F_SQUAT, F_KICK, F_PLANK, F_DOWN, F_SQUAT, F_JUMP]
NAMES = ('de pie', 'agachado', 'pies en el aire', 'plancha', 'flexion abajo', 'agachado (vuelta)', 'salto')
JF = [build_side(f) for f in FRAMES]


def dedos(J):
    """rayitas de los dedos sobre la mano apoyada en el suelo (se lee la palma plana)"""
    def f(pen):
        if not CFG['fingers']:
            return
        w_, tip = J['near_arm'][2], J['near_handtip']
        for k_ in (0.12, 0.20):
            x = tip[0] - k_
            pen.line([(x, w_[1] + 0.045), (x, w_[1] + 0.085)], w=pen.c.LI * 0.8)
    return f


AX = HX + 1.20                                  # x de las flechas verticales (delante de la cabeza / manos)
L_ = CFG['arrow_len']


def flechas(i):
    if not CFG['arrows']:
        return []
    if i == 0:    # de pie, a punto de agacharse
        return [lambda pen: draw_line_arrow(pen, (XA + 0.75, 1.55), (XA + 0.75, 1.55 - L_))]
    if i == 1:    # manos fijas, los pies saldran hacia atras
        return [lambda pen: draw_line_arrow(pen, (XA - 0.30, 0.42), (XA - 0.30 - L_, 0.42))]
    if i == 2:    # los pies vuelan hacia atras
        ya = float(JF[2]['near_leg'][2][1]); xa_ = float(JF[2]['near_leg'][2][0])
        return [lambda pen: draw_line_arrow(pen, (xa_ - 0.55, ya + 0.05), (xa_ - 0.55 - L_, ya + 0.05))]
    if i == 3:    # a punto de bajar el pecho
        return [lambda pen: draw_line_arrow(pen, (AX, 1.10), (AX, 1.10 - L_))]
    if i == 4:    # subiendo el pecho
        return [lambda pen: draw_line_arrow(pen, (AX, 0.60), (AX, 0.60 + L_))]
    if i == 5:    # pies de vuelta, a punto de saltar
        return [lambda pen: draw_line_arrow(pen, (AX, 0.80), (AX, 0.80 + L_))]
    return [lambda pen: draw_line_arrow(pen, (XA + 0.75, 1.85 + CFG['jump'] * 0.5), (XA + 0.75, 1.85 + CFG['jump'] * 0.5 + L_))]


ex = [(([dedos(JF[i])] if i in (1, 2, 3, 4, 5) else []) + flechas(i)) for i in range(7)]
_kx = float(JF[2]['near_leg'][2][0]) - 0.55 - L_                 # extremo de la flecha de los pies en el aire (la que mas a la izquierda llega)
bb = (min(-CFG['left'], _kx - 0.15), 0.0, AX + 0.2, JF[6]['hd'][1] + 0.55)     # encuadre fijo para los 7 fotogramas (flechas y salto incluidos)
imgs = render_scene(FRAMES, OUT + 'burpees', durations=[int(CFG[k]) for k in ('dur1', 'dur2', 'dur3', 'dur4', 'dur5', 'dur6', 'dur7')],
                    margin=CFG['margin'], bbox_extra=bb, extras=ex)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processBurpee)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def tilt(a, b):
    return float(np.degrees(np.arctan2(abs(b[1] - a[1]), abs(b[0] - a[0]))))


def medidas(J):
    S, H = J['S'], J['H']
    sh, el, wr = J['near_arm']; hp, kn, an = J['near_leg'][:3]
    m = dict(knee=ang3(hp, kn, an), elbow=ang3(sh, el, wr), line=ang3(S, H, an), tilt=tilt(S, H))
    m['standing'] = m['knee'] >= STAND_KNEE_MIN and m['tilt'] >= STAND_TILT_MIN
    m['inplank'] = m['tilt'] <= PLANK_MAX_TILT and m['line'] >= PLANK_LINE_MIN and m['elbow'] >= PLANK_ARM_MIN
    return m


M = [medidas(J) for J in JF]
for nm, m, J in zip(NAMES, M, JF):
    print(f"{nm:16s}| rodilla {m['knee']:4.0f}° | codo {m['elbow']:4.0f}° | hombro-cadera-tobillo {m['line']:4.0f}° | tronco {m['tilt']:3.0f}° | "
          f"{'DE PIE' if m['standing'] else 'PLANCHA' if m['inplank'] else '-'}")

# pies y manos
for i in (0, 1, 5):
    for sd in ('near', 'far'):
        assert abs(JF[i][sd + '_leg'][2][1] - AY) < 4e-3, f'{NAMES[i]}: los pies deben tocar el suelo (pie plano)'
for i in (1, 2, 3, 4, 5):
    assert np.allclose(JF[i]['near_arm'][2], (HX, WY), atol=4e-3), f'{NAMES[i]}: la mano debe estar apoyada y fija en el suelo'
for i in (3, 4):
    assert abs(feet_low(JF[i])) < 3e-3, f'{NAMES[i]}: las puntas de los pies deben tocar el suelo'
assert abs(toe_x(JF[3]) - toe_x(JF[4])) < 2e-3, 'plancha y flexion: los pies no se mueven'
# aire: pies despegados
assert min(JF[2]['near_leg'][2][1], JF[2]['far_leg'][2][1]) > AY + 0.2, 'pies en el aire: deben verse despegados del suelo'
assert feet_low(JF[2]) > 0.12, 'pies en el aire: ni las puntas tocan el suelo'
assert min(JF[6]['near_leg'][2][1], JF[6]['far_leg'][2][1]) > AY + 0.3, 'salto: los pies deben verse despegados del suelo'
# fases del contador
assert M[0]['standing'], 'de pie: rodilla >= 160 y tronco >= 55'
assert M[1]['knee'] <= DOWN_KNEE_MAX and not M[1]['inplank'] and not M[1]['standing'], 'agachado: rodilla <= 140 y todavia no plancha'
assert M[2]['inplank'], 'pies en el aire: ya cuenta como plancha (tronco <= 40, linea >= 135, brazos estirados)'
assert M[3]['inplank'] and M[3]['elbow'] >= PLANK_ARM_MIN, 'plancha: tronco <= 40, linea >= 135 y brazos estirados'
assert M[4]['elbow'] <= PUSHUP_DOWN and M[4]['tilt'] <= PLANK_MAX_TILT, 'flexion abajo: codo <= 110'
assert M[5]['elbow'] >= PUSHUP_UP and M[5]['knee'] <= DOWN_KNEE_MAX and not M[5]['standing'], 'agachado de vuelta: brazos estirados (>= 135), aun no de pie'
assert M[6]['tilt'] >= RETURN_TILT_MIN and M[6]['standing'], 'salto: tronco >= 45 y de pie'
# maquina de estados de processBurpee: top -> down -> plank -> pushdown -> plank -> up -> de pie = 1 rep
state, reps, trace = 'top', 0, []
for m in M[1:] + M[:1]:                              # un ciclo completo: agachado ... salto, de pie
    if state == 'top':
        if m['knee'] <= DOWN_KNEE_MAX: state = 'down'
    elif state == 'down':
        if m['inplank']: state = 'plank'
        elif m['standing']: state = 'top'
    elif state == 'plank':
        if m['elbow'] <= PUSHUP_DOWN: state = 'pushdown'
        elif m['tilt'] >= RETURN_TILT_MIN: state = 'up'
    elif state == 'pushdown':
        if m['elbow'] >= PUSHUP_UP: state = 'plank'
    elif state == 'up':
        if m['standing']: reps += 1; state = 'top'
    trace.append(state)
print('fases:', ' > '.join(trace), '| repeticiones contadas en un ciclo:', reps)
assert reps == 1 and state == 'top', 'un ciclo del GIF debe contar exactamente 1 repeticion'
print('OK: los burpees coinciden con los umbrales del contador (burpee, processBurpee)')
