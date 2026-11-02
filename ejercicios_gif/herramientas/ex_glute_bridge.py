"""Puente de glúteo (glute bridge), vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que crunch.gif / leg-raise.gif / weighted-crunch.gif
(mismo muñeco, estilo y suelo: ex_crunch.py / figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Técnica (Mayo Clinic, NHS, ACE): tumbado boca arriba, rodillas dobladas y pies PLANOS en el suelo, brazos a los lados con las palmas en el suelo; se empuja con los talones y se SUBE la cadera
hasta que hombros, cadera y rodillas forman una línea recta (hombros y cabeza SIGUEN en el suelo, los pies no se mueven); arriba se aprietan los glúteos; se baja la cadera al suelo.
Como lo mira la app (workout.js: processGluteBridge, counter "glutebridge", slug glute-bridge, migracion 0119). Contador PROPIO: no sube el hombro (crunch) ni se mueve el tobillo (leg raise), sube la CADERA:
  - ARMAR (posicion inicial, el GIF empieza asi): inclinacion hombro-cadera <= GLUTEBRIDGE_ARM_MAX_TILT_DEG 20°, rodilla al menos GLUTEBRIDGE_ARM_MIN_THIGH_ELEV 0.35 muslos POR ENCIMA de la cadera,
    angulo cadera-rodilla-tobillo <= GLUTEBRIDGE_ARM_MAX_KNEE_DEG 150°, cadera abajo (rawRise <= GLUTEBRIDGE_ARM_MAX_RISE 0.20 y angulo hombro-cadera-rodilla <= GLUTEBRIDGE_ARM_MAX_HIP_DEG 145°),
  - lift = rawRise - reposo, con rawRise = (altura de la cadera - altura del hombro) / muslo; ARRIBA = lift >= GLUTEBRIDGE_UP_LIFT 0.28 Y angulo hombro-cadera-rodilla >= GLUTEBRIDGE_TOP_ANGLE_DEG 148° (extension de cadera de verdad),
  - ABAJO = lift <= GLUTEBRIDGE_DOWN_LIFT 0.12 (cuenta la repeticion); el tronco nunca pasa de GLUTEBRIDGE_STAND_TILT_DEG 55° (si no, la app cree que te has levantado),
  - boca arriba (checkOnBack, sin mirar manos): rodilla NO mas de 0.45 del muslo por debajo de la cadera (aqui la rodilla siempre queda POR ENCIMA).
Los PIES y los HOMBROS no se mueven entre fotogramas (en el puente real los pies se quedan clavados y los hombros apoyados): solo sube la cadera. Para eso la posicion de hombro y tobillo es fija y la rodilla
se calcula por IK (figura.ik2), asi el muslo y la espinilla cambian de angulo a la vez que sube la cadera.
GIF de 4 fotogramas: abajo (tumbado, rodillas dobladas, pies planos, brazos a los lados) -> a medio camino -> arriba (linea recta hombros-cadera-rodillas) -> a medio camino de vuelta.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_glute_bridge.py [carpeta_salida] [clave=valor ...]   (genera glute-bridge.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t0=2, tm=-12, t1=-24, h=3, lift=-0.05, top=0.45, thigh0=127, far_dx=-0.10, far_arm=0,
           arm_a=185, arm_f=180, hand=180, margin=0.40, dur0=1200, durm=380, dur1=1400)
# t0/tm/t1: inclinacion del tronco (grados sobre la horizontal; negativo = la cadera mas alta que el hombro) abajo / a medio camino / arriba; h: angulo del cuello-cabeza (apoyada en el suelo, como crunch.gif)
# thigh0: angulo del muslo abajo (piernas dobladas con los pies planos, como crunch.gif); de ahi sale la posicion FIJA del tobillo, que ya no se mueve en ningun fotograma
# lift: cuanto se sube todo el dibujo sobre el suelo calculado (negativo = se hunde: pies, brazos y hombros tocan la linea del suelo)
# top: espacio extra por encima del muñeco en el encuadre (sube/baja el suelo en el cuadro; el suelo queda a una altura parecida a crunch.gif)
# far_dx: cuanto queda el tobillo de la pierna lejana mas a la izquierda que el cercano (para que se vean las dos); far_arm: grados de mas del brazo lejano (0 = los dos brazos EN LINEA, se ve uno solo: es de perfil)
# arm_a / arm_f / hand: angulos del brazo, antebrazo y mano (180 = hacia los pies, pegado al suelo: brazos a los lados con la palma en el suelo)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processGluteBridge / checkOnBack)
GLUTEBRIDGE_ARM_MAX_TILT_DEG = 20
GLUTEBRIDGE_ARM_MIN_THIGH_ELEV = 0.35
GLUTEBRIDGE_ARM_MAX_KNEE_DEG = 150
GLUTEBRIDGE_ARM_MAX_RISE = 0.20
GLUTEBRIDGE_ARM_MAX_HIP_DEG = 145
GLUTEBRIDGE_UP_LIFT = 0.28
GLUTEBRIDGE_TOP_ANGLE_DEG = 148
GLUTEBRIDGE_DOWN_LIFT = 0.12
GLUTEBRIDGE_STAND_TILT_DEG = 55
BACK_KNEE_BELOW_HIP_MAX_FACTOR = 0.45


# ---- pierna con el tobillo FIJO (IK) y el pie plano con la planta hacia abajo aunque apunte a la izquierda (figura.limb_leg asume un pie apoyado y apuntando a la derecha), igual que ex_crunch.py
def limb_leg_ikflat(spec, H):
    if len(spec) > 4 and spec[4] == 'ikflat':
        k, a = ik2(H, spec[1], L_THIGH, L_SHIN, spec[2])
        d = dv(spec[3]); p = np.array([0.0, -1.0])
        he = a + p * 0.10 - d * 0.07
        to = he + d * 0.44
        return H, k, a, he, to
    return _orig(spec, H)


_orig = figura.limb_leg
figura.limb_leg = limb_leg_ikflat

# ---- tobillo fijo: el de la pose "abajo" (misma pierna que crunch.gif: muslo thigh0, espinilla para que gluteo y pie queden en la misma linea de suelo)
SH = np.array([0.0, 0.0])                                                # hombro (fijo en todos los fotogramas)
H0 = SH - dv(CFG['t0'])                                                  # cadera abajo
th0 = CFG['thigh0']; drop = 0.06
sh0 = 180 + np.rad2deg(np.arcsin((drop + L_THIGH * np.sin(np.deg2rad(th0))) / L_SHIN))
ANK = H0 + L_THIGH * dv(th0) + L_SHIN * dv(sh0)                          # tobillo cercano (fijo)
ANK_FAR = ANK + np.array([CFG['far_dx'], 0.0])


def pose(torso):
    return dict(f=-1, sh=tuple(SH), torso=torso, head=CFG['h'],
                near_leg=('ik', tuple(ANK), 'cw', 180, 'ikflat'), far_leg=('ik', tuple(ANK_FAR), 'cw', 180, 'ikflat'),
                near_arm=('fk', CFG['arm_a'], CFG['arm_f']), far_arm=('fk', CFG['arm_a'] + CFG['far_arm'], CFG['arm_f'] + CFG['far_arm']),
                near_hand=CFG['hand'], far_hand=CFG['hand'] + CFG['far_arm'])


FRAMES = [pose(CFG['t0']), pose(CFG['tm']), pose(CFG['t1']), pose(CFG['tm'])]
# el suelo se calcula UNA vez con la pose de abajo y se aplica igual a todos los fotogramas (hombros y pies no se mueven)
DY = ground_shift(build_side(FRAMES[0])) + CFG['lift']
for f_ in FRAMES:
    f_['ground'] = False; f_['dy'] = DY

# encuadre fijo para los 4 fotogramas (con algo de aire por encima, como crunch.gif)
_pts = np.vstack([all_points(shift_J(build_side(f_), DY)) for f_ in FRAMES]); _x0, _y0 = _pts.min(0); _x1, _y1 = _pts.max(0)
BB = (_x0, min(_y0 - 0.25, 0), _x1, _y1 + CFG['top'])



# ---- el suelo TAPA lo que queda por debajo de su linea: abajo la espalda/cadera se hunde en el suelo (no se ve la espalda, parece que el cuerpo toca el suelo) y al subir la cadera la espalda si se ve
def floor_cover(pen):
    fy = pen.c.C((0, -0.055))[1]
    y0 = int(round(fy + 1.2 * SS))
    pen.img[y0:, :] = 255
    cv2.line(pen.img, (0, int(fy)), (CW * SS, int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)


render_scene(FRAMES, OUT + 'glute-bridge', durations=[int(CFG['dur0']), int(CFG['durm']), int(CFG['dur1']), int(CFG['durm'])], margin=CFG['margin'], bbox_extra=BB,
             extras=[[floor_cover] for _ in FRAMES])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processGluteBridge / checkOnBack)
def final_J(fr):
    return shift_J(build_side(fr), DY)


def angle3(a, b, c):
    """angulo en b (grados) entre b->a y b->c, como angle() de la app"""
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


JS = [final_J(f) for f in FRAMES]


def metrics(J, sd='near'):
    S, H = J['S'], J['H']
    _, kn, an = J[sd + '_leg'][:3]
    thigh = float(np.linalg.norm(H - kn))
    return dict(tilt=float(np.degrees(np.arctan2(abs(S[1] - H[1]), abs(S[0] - H[0])))),
                hip=angle3(S, H, kn), knee=angle3(H, kn, an), elev=(kn[1] - H[1]) / thigh,   # app: (cadera.y - rodilla.y) / muslo (y hacia abajo)
                rise=(H[1] - S[1]) / thigh,                                                    # app: (hombro.y - cadera.y) / muslo
                ank=an, sh=S)


M = [metrics(J) for J in JS]
base = M[0]['rise']
for i, nm in enumerate(('abajo', 'medio (sube)', 'arriba', 'medio (baja)')):
    m = M[i]; lift = m['rise'] - base
    print(f"{nm}: inclinacion {m['tilt']:.0f}°, rodilla sobre cadera {m['elev']:.2f} muslos, cadera {m['hip']:.0f}°, rodilla {m['knee']:.0f}°, subida de cadera (lift) {lift:.2f}")
    assert m['tilt'] <= GLUTEBRIDGE_STAND_TILT_DEG, f'{nm}: el tronco no puede pasar de {GLUTEBRIDGE_STAND_TILT_DEG}° (la app cree que te has levantado)'
    assert m['elev'] > -BACK_KNEE_BELOW_HIP_MAX_FACTOR, f'{nm}: boca arriba, la rodilla no puede quedar por debajo de la cadera'
    assert np.allclose(m['ank'], M[0]['ank'], atol=1e-6) and np.allclose(m['sh'], M[0]['sh'], atol=1e-6), f'{nm}: pies y hombros no se mueven'
    if i == 0:
        assert m['tilt'] <= GLUTEBRIDGE_ARM_MAX_TILT_DEG, f'abajo: tumbado para armar (<= {GLUTEBRIDGE_ARM_MAX_TILT_DEG}°)'
        assert m['elev'] >= GLUTEBRIDGE_ARM_MIN_THIGH_ELEV, f'abajo: rodilla >= {GLUTEBRIDGE_ARM_MIN_THIGH_ELEV} muslos sobre la cadera'
        assert m['knee'] <= GLUTEBRIDGE_ARM_MAX_KNEE_DEG, f'abajo: rodilla doblada (<= {GLUTEBRIDGE_ARM_MAX_KNEE_DEG}°)'
        assert m['rise'] <= GLUTEBRIDGE_ARM_MAX_RISE, f'abajo: cadera abajo (rawRise <= {GLUTEBRIDGE_ARM_MAX_RISE})'
        assert m['hip'] <= GLUTEBRIDGE_ARM_MAX_HIP_DEG, f'abajo: cadera flexionada (<= {GLUTEBRIDGE_ARM_MAX_HIP_DEG}°)'
        assert lift <= GLUTEBRIDGE_DOWN_LIFT, 'abajo: lift <= GLUTEBRIDGE_DOWN_LIFT'
    if i == 2:
        assert lift >= GLUTEBRIDGE_UP_LIFT, f'arriba: lift >= {GLUTEBRIDGE_UP_LIFT}'
        assert m['hip'] >= GLUTEBRIDGE_TOP_ANGLE_DEG, f'arriba: cadera extendida (hombro-cadera-rodilla >= {GLUTEBRIDGE_TOP_ANGLE_DEG}°)'
# hombros y cabeza siguen en el suelo arriba: el hombro no sube respecto a abajo (es el mismo punto fijo, comprobado arriba) y la cabeza tampoco cambia
print('OK: el puente de glúteo coincide con los umbrales del contador (glutebridge, processGluteBridge)')
