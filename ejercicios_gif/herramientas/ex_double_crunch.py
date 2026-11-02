"""Doble crunch, vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que crunch.gif
(mismo muñeco, estilo y suelo: ex_crunch.py / figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app (workout.js: processDoubleCrunch, counter "doublecrunch", slug double-crunch):
  - el TORSO se queda LEVANTADO todo el rato (inclinacion hombro-cadera entre DOUBLECRUNCH_TILT_MIN_DEG 30° y DOUBLECRUNCH_TILT_MAX_DEG 68°, nunca del todo tumbado),
  - lo que cuenta es la distancia RODILLA-HOMBRO en proporcion al torso (hombro-cadera):
      ESTIRADO (kneeToShoulder >= DOUBLECRUNCH_EXTEND_MIN_FACTOR 1.1, y < DOUBLECRUNCH_STAND_MAX_FACTOR 2.0) = piernas estiradas en el aire, es la posicion inicial;
      DOBLADO  (kneeToShoulder <= DOUBLECRUNCH_TUCK_MAX_FACTOR 0.7) = rodillas al pecho; al volver a estirar se cuenta la repeticion,
  - boca arriba (checkOnBack, sin mirar manos ni cara): rodilla NO mas de 0.45 del muslo por debajo de la cadera.
GIF de 2 fotogramas: estirado (torso reclinado ~38°, piernas estiradas en el aire) -> doblado (torso mas incorporado, rodillas al pecho). Manos detras de la nuca como crunch.gif.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_double_crunch.py [carpeta_salida] [clave=valor ...]   (genera double-crunch.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t0=38, h0=62, t1=62, h1=84, th0=166, sh0=167, th1=100, sh1=202, far0=6, far1=-6, foot0=22, foot1=30,
           du=0.05, dn=-0.28, margin=0.40, dur0=1300, dur1=1200)
# t0/t1: inclinacion del torso (grados sobre la horizontal) estirado / doblado; h0/h1: angulo de la cabeza (sube con el torso, como crunch.gif)
# th/sh: angulo del muslo y de la espinilla (grados matematicos; 180 = hacia la izquierda, 90 = arriba); far0/far1: grados de mas de la pierna lejana (estirado / doblado), para que se vean las dos
# foot0/foot1: cuanto apunta el pie hacia delante (flexion plantar) respecto a 90° con la espinilla; du/dn: manos detras de la nuca (como ex_crunch.py)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processDoubleCrunch / checkOnBack)
DOUBLECRUNCH_TILT_MIN_DEG = 30
DOUBLECRUNCH_TILT_MAX_DEG = 68
DOUBLECRUNCH_EXTEND_MIN_FACTOR = 1.1
DOUBLECRUNCH_TUCK_MAX_FACTOR = 0.7
DOUBLECRUNCH_STAND_MAX_FACTOR = 2.0
BACK_KNEE_BELOW_HIP_MAX_FACTOR = 0.45


# ---- pie en el aire: la planta mira "hacia fuera" de la espinilla (figura.limb_leg asume un pie apoyado y apuntando a la derecha)
def limb_leg_air(spec, H):
    if len(spec) > 4 and spec[4] == 'air':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        s = dv(spec[2])
        d = rot(s, -90 + spec[3])        # direccion talon -> puntera: perpendicular a la espinilla, hacia el vientre, algo estirada
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

render_scene(FRAMES, OUT + 'double-crunch', durations=[int(CFG['dur0']), int(CFG['dur1'])], margin=CFG['margin'])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processDoubleCrunch / checkOnBack)
def final_J(fr):
    J = build_side(fr)
    return shift_J(J, ground_shift(J) + fr.get('dy', 0))


for i, nm in enumerate(('estirado', 'doblado')):
    J = final_J(FRAMES[i])
    S, H = J['S'], J['H']
    torso = float(np.linalg.norm(S - H))
    tilt = float(np.degrees(np.arctan2(abs(S[1] - H[1]), abs(S[0] - H[0]))))
    assert DOUBLECRUNCH_TILT_MIN_DEG <= tilt <= DOUBLECRUNCH_TILT_MAX_DEG, f'{nm}: el torso debe quedar en la banda {DOUBLECRUNCH_TILT_MIN_DEG}-{DOUBLECRUNCH_TILT_MAX_DEG}° (levantado, no tumbado)'
    out = [f"{nm}: inclinacion torso {tilt:.0f}° (banda {DOUBLECRUNCH_TILT_MIN_DEG}-{DOUBLECRUNCH_TILT_MAX_DEG})"]
    for sd in ('near', 'far'):
        kn = J[sd + '_leg'][1]
        thigh = float(np.linalg.norm(H - kn))
        k2s = float(np.linalg.norm(kn - S)) / torso                  # app: kneeToShoulder = dist(rodilla, hombro) / largo del torso
        below = (H[1] - kn[1]) / thigh                                # app: (rodilla.y - cadera.y) / muslo (y hacia abajo)
        assert below < BACK_KNEE_BELOW_HIP_MAX_FACTOR, f'{nm}/{sd}: boca arriba, la rodilla no puede quedar por debajo de la cadera'
        if i == 0:
            assert DOUBLECRUNCH_EXTEND_MIN_FACTOR <= k2s < DOUBLECRUNCH_STAND_MAX_FACTOR, f'{nm}/{sd}: piernas estiradas (rodilla-hombro >= 1.1 y < 2.0)'
        else:
            assert k2s <= DOUBLECRUNCH_TUCK_MAX_FACTOR, f'{nm}/{sd}: rodillas al pecho (rodilla-hombro <= 0.7)'
        out.append(f"{sd}: rodilla-hombro {k2s:.2f} torsos, rodilla sobre cadera {-below:.2f} muslos")
    print(' | '.join(out))
print('OK: el doble crunch coincide con los umbrales del contador (doublecrunch, processDoubleCrunch)')
