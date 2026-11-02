"""Scissor Kicks (tijeretas), vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que crunch.gif / double-crunch.gif / leg-raise.gif
(mismo muñeco, estilo y suelo: ex_leg_raise.py / figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app (workout.js: processScissor, counter "scissor", slug scissor-kick):
  - el TORSO se queda tumbado (inclinacion hombro-cadera <= SCISSOR_ARM_MAX_TILT_DEG 55°), cabeza ligeramente levantada, manos detras de la nuca,
  - la cadera es la referencia de altura "0"; se mide cuanto sube cada TOBILLO sobre ella, en proporcion al muslo:
      para ARMAR basta UNA pierna con el tobillo >= SCISSOR_ARM_LIFT_FACTOR 0.20 muslos por encima de la cadera (y <= SCISSOR_ARM_MAX_FACTOR 2.5),
      la otra queda "a un palmo" del suelo (>= SCISSOR_LIFT_MIN_FACTOR 0.10; si las dos bajan de SCISSOR_REST_MAX_FACTOR 0.10 la serie se cierra),
  - lo que cuenta es el VAIVEN de la diferencia de alturas entre las dos piernas (>= SCISSOR_SWING_INITIAL 0.25 muslos): cada cambio de pierna arriba es medio ciclo,
  - piernas ESTIRADAS todo el rato (rodilla cadera-rodilla-tobillo >= 155°, como leg-raise), boca arriba (checkOnBack, sin mirar manos): rodilla NO mas de 0.45 del muslo por debajo de la cadera.
GIF de 4 fotogramas: pierna cercana arriba / lejana abajo -> las piernas se cruzan -> se intercambian -> se cruzan de vuelta (el torso NO se mueve).
Pies IGUAL que en crunch.gif (ex_crunch.py: pie plano, planta hacia abajo, puntera a la izquierda).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_scissor_kick.py [carpeta_salida] [clave=valor ...]   (genera scissor-kick.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t=2, h=10, hi=146, lo=172, spread=1, foot=180, mid=159, mspread=3,
           du=0.05, dn=-0.28, margin=0.40, top=0.95, dur0=600, dur1=170)
# t: inclinacion del torso (no se mueve); h: angulo de la cabeza (ligeramente levantada, como leg-raise.gif)
# hi/lo: angulo del muslo de la pierna ALTA / BAJA (grados matematicos; 180 = hacia la izquierda, 90 = arriba); spread: grados de mas de la espinilla sobre el muslo
# foot: direccion del pie (180 = puntera a la izquierda, como crunch); mid/mspread: angulo del muslo al cruzarse las piernas y separacion entre ellas en ese momento
# du/dn: manos detras de la nuca (como ex_leg_raise.py); top: hueco extra arriba para que el suelo quede a la misma altura que en crunch.gif; dur0/dur1: ms de los extremos / del cruce
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processScissor / checkOnBack)
SCISSOR_LIFT_MIN_FACTOR = 0.10
SCISSOR_ARM_LIFT_FACTOR = 0.20
SCISSOR_ARM_MAX_FACTOR = 2.5
SCISSOR_ARM_MAX_TILT_DEG = 55
SCISSOR_REST_MAX_FACTOR = 0.10
SCISSOR_SWING_INITIAL = 0.25
LEG_STRAIGHT_MIN_DEG = 155
BACK_KNEE_BELOW_HIP_MAX_FACTOR = 0.45


# ---- pie IGUAL que en crunch.gif (ex_crunch.py: limb_leg_flat): pie plano, planta hacia abajo y puntera hacia la izquierda, aunque la pierna este en el aire
def limb_leg_flat(spec, H):
    if len(spec) > 4 and spec[4] == 'flat':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        d = dv(spec[3]); p = np.array([0.0, -1.0])
        he = a + p * 0.10 - d * 0.07
        to = he + d * 0.44
        return H, k, a, he, to
    return _orig(spec, H)


_orig = figura.limb_leg
figura.limb_leg = limb_leg_flat


def pose(near_th, far_th):
    """near_th/far_th: angulo del muslo de cada pierna (la espinilla +spread, estirada)."""
    leg = lambda th: ('fk', th, th + CFG['spread'], CFG['foot'], 'flat')
    return dict(f=-1, hip=(0, 0.3), torso=CFG['t'], head=CFG['h'], near_leg=leg(near_th), far_leg=leg(far_th),
                near_arm=('ikh', CFG['du'], CFG['dn'], 'ccw'), far_arm=('ikh', CFG['du'] + 0.03, CFG['dn'] + 0.02, 'ccw'))


hi, lo, mid, ms = CFG['hi'], CFG['lo'], CFG['mid'], CFG['mspread']
# 0: cercana arriba | 1: cruce (cercana baja) | 2: lejana arriba | 3: cruce (cercana sube)
FRAMES = [pose(hi, lo), pose(mid, mid + ms), pose(lo, hi), pose(mid, mid - ms)]
DURS = [int(CFG['dur0']), int(CFG['dur1']), int(CFG['dur0']), int(CFG['dur1'])]

# encuadre fijo (suelo a la misma altura que crunch.gif): hueco extra por encima
_pts = []
for fr in FRAMES:
    J_ = build_side(fr); J_ = shift_J(J_, ground_shift(J_)); _pts.append(all_points(J_))
_pts = np.vstack(_pts); _x0, _y0 = _pts.min(0); _x1, _y1 = _pts.max(0)
BB = (_x0, min(_y0 - 0.25, 0), _x1, _y1 + CFG['top'])
render_scene(FRAMES, OUT + 'scissor-kick', durations=DURS, margin=CFG['margin'], bbox_extra=BB)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processScissor / checkOnBack)
def final_J(fr):
    J = build_side(fr)
    return shift_J(J, ground_shift(J) + fr.get('dy', 0))


def angle3(a, b, c):
    """angulo en b (grados) entre b->a y b->c, como angle() de la app"""
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


diffs = []
for i, nm in enumerate(('cercana arriba', 'cruce', 'lejana arriba', 'cruce')):
    J = final_J(FRAMES[i])
    S, H = J['S'], J['H']
    tilt = float(np.degrees(np.arctan2(abs(S[1] - H[1]), abs(S[0] - H[0]))))
    assert tilt <= SCISSOR_ARM_MAX_TILT_DEG, f'{nm}: el torso debe quedar tumbado (inclinacion <= {SCISSOR_ARM_MAX_TILT_DEG}°)'
    lifts = {}
    out = [f"{i} {nm}: torso {tilt:.0f}°"]
    for sd in ('near', 'far'):
        _, kn, an = J[sd + '_leg'][:3]
        thigh = float(np.linalg.norm(H - kn))
        lift = (an[1] - H[1]) / thigh                  # app: (cadera.y - tobillo.y) / muslo (y hacia abajo)
        knee_a = angle3(H, kn, an)                     # app: kneeAngle = angle(cadera, rodilla, tobillo)
        below = (H[1] - kn[1]) / thigh                 # app: (rodilla.y - cadera.y) / muslo
        assert knee_a >= LEG_STRAIGHT_MIN_DEG, f'{nm}/{sd}: piernas estiradas (rodilla >= {LEG_STRAIGHT_MIN_DEG}°)'
        assert below < BACK_KNEE_BELOW_HIP_MAX_FACTOR, f'{nm}/{sd}: boca arriba, la rodilla no puede quedar por debajo de la cadera'
        assert lift >= SCISSOR_LIFT_MIN_FACTOR, f'{nm}/{sd}: ninguna pierna pegada al suelo (tobillo >= {SCISSOR_LIFT_MIN_FACTOR} muslos sobre la cadera)'
        lifts[sd] = lift
        out.append(f"{sd}: tobillo {lift:.2f} muslos, rodilla {knee_a:.0f}°")
    top = max(lifts.values())
    assert SCISSOR_ARM_LIFT_FACTOR <= top <= SCISSOR_ARM_MAX_FACTOR, f'{nm}: una pierna claramente levantada para armar (0.20-2.5 muslos)'
    assert not (lifts['near'] < SCISSOR_REST_MAX_FACTOR and lifts['far'] < SCISSOR_REST_MAX_FACTOR), f'{nm}: las dos piernas abajo cerrarian la serie'
    diffs.append(lifts['near'] - lifts['far'])
    print(' | '.join(out))
swing = abs(diffs[0] - diffs[2])
assert diffs[0] > 0 > diffs[2], 'las piernas deben alternar cual esta arriba'
assert abs(diffs[1]) < abs(diffs[0]) and abs(diffs[3]) < abs(diffs[0]), 'en los fotogramas de cruce las piernas deben estar mas juntas que en los extremos'
assert swing >= SCISSOR_SWING_INITIAL, f'el vaiven entre extremos debe superar {SCISSOR_SWING_INITIAL} muslos'
print(f'vaiven de la diferencia entre piernas: {swing:.2f} muslos (>= {SCISSOR_SWING_INITIAL})')
print('OK: las tijeretas coinciden con los umbrales del contador (scissor, processScissor)')
