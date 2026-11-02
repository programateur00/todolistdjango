"""Elevación de piernas (leg raise), vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que crunch.gif / double-crunch.gif
(mismo muñeco, estilo y suelo: ex_crunch.py / ex_double_crunch.py / figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app (workout.js: processLegRaise, counter "legraise", slug leg-raise):
  - el TORSO se queda en el suelo todo el rato (inclinacion hombro-cadera <= ON_GROUND_ARM_MAX_TILT_DEG 20° para armar, <= ON_GROUND_MAX_TILT_DEG 40° durante la serie),
    con la cabeza ligeramente levantada del suelo (lo pide el aviso de la app),
  - lo que cuenta es el ANGULO DE CADERA (hombro-cadera-tobillo):
      ABAJO  (>= LEG_RAISE_DOWN_ANGLE_DEG 165°) = piernas estiradas en el suelo, en linea con el torso, es la posicion inicial;
      ARRIBA (<= LEG_RAISE_UP_ANGLE_DEG 100°)   = piernas levantadas; al volver a bajar (>= 165°) se cuenta la repeticion,
  - las piernas tienen que ir ESTIRADAS (angulo de rodilla cadera-rodilla-tobillo >= LEG_RAISE_STRAIGHT_MIN_DEG 155°) para armar,
  - boca arriba (checkOnBack, sin mirar manos): rodilla NO mas de 0.45 del muslo por debajo de la cadera.
GIF de 2 fotogramas: abajo (piernas estiradas en el suelo, manos detras de la nuca como crunch.gif) -> arriba (piernas estiradas en vertical, torso quieto).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_leg_raise.py [carpeta_salida] [clave=valor ...]   (genera leg-raise.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t0=2, h0=10, t1=2, h1=10, th0=181, sh0=182, th1=92, sh1=93, far0=-1.5, far1=4, foot0=18, foot1=18,
           du=0.05, dn=-0.28, margin=0.40, dur0=1300, dur1=1200)
# t0/t1: inclinacion del torso (grados sobre la horizontal) abajo / arriba (no se mueve); h0/h1: angulo de la cabeza (ligeramente levantada, como crunch.gif)
# th/sh: angulo del muslo y de la espinilla (grados matematicos; 180 = hacia la izquierda, 90 = arriba); far0/far1: grados de mas de la pierna lejana (abajo / arriba), para que se vean las dos
# foot0/foot1: cuanto apunta el pie respecto a 90° con la espinilla (flexion plantar); du/dn: manos detras de la nuca (como ex_crunch.py / ex_double_crunch.py)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processLegRaise / checkOnBack)
LEG_RAISE_DOWN_ANGLE_DEG = 165
LEG_RAISE_UP_ANGLE_DEG = 100
LEG_RAISE_STRAIGHT_MIN_DEG = 155
ON_GROUND_ARM_MAX_TILT_DEG = 20
ON_GROUND_MAX_TILT_DEG = 40
BACK_KNEE_BELOW_HIP_MAX_FACTOR = 0.45


# ---- pie "en el aire" / apoyado de talon: la planta mira hacia fuera de la espinilla (figura.limb_leg asume un pie apoyado y apuntando a la derecha), igual que ex_double_crunch.py
def limb_leg_air(spec, H):
    if len(spec) > 4 and spec[4] == 'air':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        s = dv(spec[2])
        d = rot(s, -90 + spec[3])        # direccion talon -> puntera: perpendicular a la espinilla, hacia la cabeza, algo estirada
        p = rot(d, 90)                   # hacia donde mira la planta (hacia fuera de la espinilla)
        he = a + p * 0.10 - d * 0.07
        to = he + d * 0.44
        return H, k, a, he, to
    return _orig(spec, H)


_orig = figura.limb_leg
figura.limb_leg = limb_leg_air


def pose(torso, head, th, sh, foot, far):
    return dict(f=-1, hip=(0, 0.3), torso=torso, head=head,
                near_leg=('fk', th, sh, foot, 'air'), far_leg=('fk', th + far, sh + far, foot, 'air'),
                near_arm=('ikh', CFG['du'], CFG['dn'], 'ccw'), far_arm=('ikh', CFG['du'] + 0.03, CFG['dn'] + 0.02, 'ccw'))


FRAMES = [pose(CFG['t0'], CFG['h0'], CFG['th0'], CFG['sh0'], CFG['foot0'], CFG['far0']),
          pose(CFG['t1'], CFG['h1'], CFG['th1'], CFG['sh1'], CFG['foot1'], CFG['far1'])]

render_scene(FRAMES, OUT + 'leg-raise', durations=[int(CFG['dur0']), int(CFG['dur1'])], margin=CFG['margin'])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processLegRaise / checkOnBack)
def final_J(fr):
    J = build_side(fr)
    return shift_J(J, ground_shift(J) + fr.get('dy', 0))


def angle3(a, b, c):
    """angulo en b (grados) entre b->a y b->c, como angle() de la app"""
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


for i, nm in enumerate(('abajo', 'arriba')):
    J = final_J(FRAMES[i])
    S, H = J['S'], J['H']
    tilt = float(np.degrees(np.arctan2(abs(S[1] - H[1]), abs(S[0] - H[0]))))
    assert tilt <= ON_GROUND_ARM_MAX_TILT_DEG, f'{nm}: el torso debe quedar tumbado (inclinacion <= {ON_GROUND_ARM_MAX_TILT_DEG}°)'
    out = [f"{nm}: inclinacion torso {tilt:.0f}° (<= {ON_GROUND_ARM_MAX_TILT_DEG})"]
    for sd in ('near', 'far'):
        _, kn, an = J[sd + '_leg'][:3]
        hip_a = angle3(S, H, an)                       # app: hipAngle = angle(hombro, cadera, tobillo)
        knee_a = angle3(H, kn, an)                     # app: kneeAngle = angle(cadera, rodilla, tobillo)
        thigh = float(np.linalg.norm(H - kn))
        below = (H[1] - kn[1]) / thigh                 # app: (rodilla.y - cadera.y) / muslo (y hacia abajo)
        assert knee_a >= LEG_RAISE_STRAIGHT_MIN_DEG, f'{nm}/{sd}: piernas estiradas (rodilla >= {LEG_RAISE_STRAIGHT_MIN_DEG}°)'
        assert below < BACK_KNEE_BELOW_HIP_MAX_FACTOR, f'{nm}/{sd}: boca arriba, la rodilla no puede quedar por debajo de la cadera'
        if i == 0:
            assert hip_a >= LEG_RAISE_DOWN_ANGLE_DEG, f'{nm}/{sd}: piernas abajo (cadera >= {LEG_RAISE_DOWN_ANGLE_DEG}°)'
        else:
            assert hip_a <= LEG_RAISE_UP_ANGLE_DEG, f'{nm}/{sd}: piernas arriba (cadera <= {LEG_RAISE_UP_ANGLE_DEG}°)'
        out.append(f"{sd}: cadera {hip_a:.0f}° rodilla {knee_a:.0f}° rodilla sobre cadera {-below:.2f} muslos")
    print(' | '.join(out))
print('OK: la elevación de piernas coincide con los umbrales del contador (legraise, processLegRaise)')
