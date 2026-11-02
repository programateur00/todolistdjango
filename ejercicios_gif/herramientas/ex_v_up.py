"""V-ups, vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que crunch.gif / double-crunch.gif / leg-raise.gif / scissor-kick.gif
(mismo muñeco, estilo y suelo: ex_leg_raise.py / figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app (workout.js: processVUp, counter "vup", slug v-up):
  - POSICION INICIAL ("abajo"): tumbado boca arriba (torso <= ON_GROUND_ARM_MAX_TILT_DEG 20°), brazos estirados POR ENCIMA DE LA CABEZA, piernas rectas
    (rodilla >= VUP_STRAIGHT_MIN_DEG 155°) y abajo (angulo de cadera hombro-cadera-tobillo >= VUP_DOWN_HIP_ANGLE_DEG 150°; las piernas pueden quedar a un palmo del suelo),
  - ARRIBA (la V): se suben A LA VEZ el torso entero y las piernas RECTAS; las tres cosas tienen que cumplirse en lo alto de la repeticion:
      torso levantado >= VUP_TOP_TORSO_TILT_DEG 35° sobre la horizontal, pierna (cadera-tobillo) >= VUP_TOP_LEG_ELEV_DEG 30° sobre la horizontal,
      rodilla >= VUP_TOP_KNEE_MIN_DEG 140° (con la V ya cerrada, cadera <= VUP_TOP_NEAR_HIP_ANGLE_DEG 115°: si no, serian rodillas al pecho),
      y las MANOS llegan a los talones: distancia muneca-tobillo <= VUP_REACH_MAX_FACTOR 0.7 largos de torso,
  - la repeticion se cuenta al volver abajo (cadera >= 150°); boca arriba (checkOnBack, sin mirar manos): rodilla NO mas de 0.45 del muslo por debajo de la cadera.
GIF de 4 fotogramas: abajo (brazos sobre la cabeza, piernas estiradas a un palmo del suelo) -> a medio camino (torso y piernas suben a la vez, los brazos pasan por la vertical)
-> la V (torso y piernas rectas en alto, manos a los tobillos/pies) -> a medio camino de vuelta.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_v_up.py [carpeta_salida] [clave=valor ...]   (genera v-up.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t0=3, h0=9, t1=62, h1=68, tm=32, hm=38,          # torso / cabeza abajo, en la V y a medio camino
           th0=174, sh0=173.5, th1=121, sh1=121, thm=149, shm=149,   # muslo / espinilla (grados matematicos; 180 = hacia la izquierda, 90 = arriba)
           far0=-2, far1=4, farm=3, foot=20,                  # grados de mas de la pierna lejana en cada fotograma y flexion plantar
           ph0=36, phm=102, r=1.16, fr=-0.04, fph=3,           # brazos: direccion hombro->muneca abajo / a medio camino (la de la V se calcula hacia el tobillo), largo, ajuste del brazo lejano
           margin=0.40, dur0=1100, dur1=1100, durm=220)
# ph0/phm: direccion (grados matematicos) del brazo cercano: 36 = estirado sobre la cabeza, un poco levantado para no tapar la cabeza (a la derecha), 90 = vertical; en la V el brazo apunta al tobillo (se calcula con la geometria)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processVUp / checkOnBack)
VUP_DOWN_HIP_ANGLE_DEG = 150
VUP_ENTER_HIP_ANGLE_DEG = 140
VUP_STRAIGHT_MIN_DEG = 155
VUP_TOP_TORSO_TILT_DEG = 35
VUP_TOP_LEG_ELEV_DEG = 30
VUP_TOP_KNEE_MIN_DEG = 140
VUP_TOP_NEAR_HIP_ANGLE_DEG = 115
VUP_REACH_MAX_FACTOR = 0.7
VUP_STAND_MIN_TILT_DEG = 70
ON_GROUND_ARM_MAX_TILT_DEG = 20
BACK_KNEE_BELOW_HIP_MAX_FACTOR = 0.45


# ---- pie "en el aire": la planta mira hacia fuera de la espinilla (figura.limb_leg asume un pie apoyado y apuntando a la derecha), igual que ex_leg_raise.py / ex_double_crunch.py
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


def joints(t, th, sh):
    """cadera, hombro y tobillo (antes de bajar al suelo) para hallar hacia donde apunta el brazo en la V"""
    H = np.array([0.0, 0.3]); S = H + dv(t)
    return S, H + dv(th) * L_THIGH + dv(sh) * L_SHIN


def arm_spec(phi, r, bend='ccw'):
    return ('ikr', tuple(r * dv(phi)), bend)


# direccion hombro -> tobillo en la V: asi las manos apuntan a los talones
S1, A1 = joints(CFG['t1'], CFG['th1'], CFG['sh1'])
ph1 = ang(A1 - S1)


def pose(t, h, th, sh, far, phi):
    return dict(f=-1, hip=(0, 0.3), torso=t, head=h,
                near_leg=('fk', th, sh, CFG['foot'], 'air'), far_leg=('fk', th + far, sh + far, CFG['foot'], 'air'),
                near_arm=arm_spec(phi, CFG['r']), far_arm=arm_spec(phi + CFG['fph'], CFG['r'] + CFG['fr']))


FRAMES = [pose(CFG['t0'], CFG['h0'], CFG['th0'], CFG['sh0'], CFG['far0'], CFG['ph0']),
          pose(CFG['tm'], CFG['hm'], CFG['thm'], CFG['shm'], CFG['farm'], CFG['phm']),
          pose(CFG['t1'], CFG['h1'], CFG['th1'], CFG['sh1'], CFG['far1'], ph1),
          pose(CFG['tm'], CFG['hm'], CFG['thm'], CFG['shm'], CFG['farm'], CFG['phm'])]
DURS = [int(CFG['dur0']), int(CFG['durm']), int(CFG['dur1']), int(CFG['durm'])]

render_scene(FRAMES, OUT + 'v-up', durations=DURS, margin=CFG['margin'])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processVUp / checkOnBack)
def final_J(fr):
    J = build_side(fr)
    return shift_J(J, ground_shift(J) + fr.get('dy', 0))


def angle3(a, b, c):
    """angulo en b (grados) entre b->a y b->c, como angle() de la app"""
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


def tilt_h(a, b):
    """inclinacion respecto a la horizontal (tiltFromHorizontal de la app)"""
    return float(np.degrees(np.arctan2(abs(a[1] - b[1]), abs(a[0] - b[0]))))


for i, nm in enumerate(('abajo', 'medio (subiendo)', 'V', 'medio (bajando)')):
    J = final_J(FRAMES[i])
    S, H = J['S'], J['H']
    tilt = tilt_h(S, H)
    torso = float(np.linalg.norm(S - H))
    out = [f"{i + 1} {nm}: torso {tilt:.0f}°"]
    reaches = []
    for sd in ('near', 'far'):
        _, kn, an, he, to = J[sd + '_leg']
        wr = J[sd + '_arm'][2]
        hip_a = angle3(S, H, an); knee_a = angle3(H, kn, an); elev = tilt_h(H, an)
        below = (H[1] - kn[1]) / float(np.linalg.norm(H - kn))          # app: (rodilla.y - cadera.y) / muslo (y hacia abajo)
        reach = float(np.linalg.norm(wr - an)) / torso                  # app: dist(muneca, tobillo) / largo del torso
        assert below < BACK_KNEE_BELOW_HIP_MAX_FACTOR, f'{nm}/{sd}: boca arriba, la rodilla no puede quedar por debajo de la cadera'
        assert min(an[1], he[1], to[1], kn[1] - 0.13) >= -1e-6, f'{nm}/{sd}: el pie no puede atravesar el suelo'
        assert tilt < VUP_STAND_MIN_TILT_DEG, f'{nm}: el torso no puede pasar de {VUP_STAND_MIN_TILT_DEG}° (seria "de pie" y cerraria la serie)'
        if i == 0:
            assert tilt <= ON_GROUND_ARM_MAX_TILT_DEG, f'{nm}: tumbado para armar (torso <= {ON_GROUND_ARM_MAX_TILT_DEG}°)'
            assert knee_a >= VUP_STRAIGHT_MIN_DEG, f'{nm}/{sd}: piernas rectas para armar (rodilla >= {VUP_STRAIGHT_MIN_DEG}°)'
            assert hip_a >= VUP_DOWN_HIP_ANGLE_DEG, f'{nm}/{sd}: cuerpo abajo (cadera >= {VUP_DOWN_HIP_ANGLE_DEG}°)'
        elif i == 2:
            assert tilt >= VUP_TOP_TORSO_TILT_DEG, f'{nm}: torso levantado (>= {VUP_TOP_TORSO_TILT_DEG}°)'
            assert elev >= VUP_TOP_LEG_ELEV_DEG, f'{nm}/{sd}: piernas levantadas (>= {VUP_TOP_LEG_ELEV_DEG}°)'
            assert hip_a <= VUP_TOP_NEAR_HIP_ANGLE_DEG, f'{nm}/{sd}: V cerrada (cadera <= {VUP_TOP_NEAR_HIP_ANGLE_DEG}°)'
            assert knee_a >= VUP_TOP_KNEE_MIN_DEG, f'{nm}/{sd}: piernas rectas arriba (rodilla >= {VUP_TOP_KNEE_MIN_DEG}°, si no son rodillas al pecho)'
            assert reach <= VUP_REACH_MAX_FACTOR, f'{nm}/{sd}: manos a los talones (muneca-tobillo <= {VUP_REACH_MAX_FACTOR} torsos)'
        else:
            assert hip_a <= VUP_ENTER_HIP_ANGLE_DEG, f'{nm}/{sd}: ya empezada la repeticion (cadera <= {VUP_ENTER_HIP_ANGLE_DEG}°)'
        out.append(f"{sd}: cadera {hip_a:.0f}°, rodilla {knee_a:.0f}°, pierna {elev:.0f}°, manos-talon {reach:.2f}")
    print(' | '.join(out))
print('OK: el V-up coincide con los umbrales del contador (vup, processVUp)')
