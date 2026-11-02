"""Weighted crunch (crunch con peso), vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que crunch.gif
(mismo muñeco, estilo, suelo, piernas dobladas con los pies planos: ex_crunch.py / figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Lo unico distinto del crunch: en vez de las manos detras de la nuca, los BRAZOS van ESTIRADOS hacia el techo y las MANOS agarran una MANCUERNA (peso) encima del pecho;
el peso sube con los brazos al subir los hombros.
Como lo mira la app (workout.js: processCrunch, counter "crunch", slug weighted-crunch, migracion 0099; mismo contador que crunch, no se toca workout.js):
  - cuenta cuanto sube el HOMBRO sobre la CADERA, en proporcion al largo del muslo: lift = (cadera.y - hombro.y) / muslo;
    ABAJO (tumbado) lift <= CRUNCH_DOWN_FACTOR = 0.05, ARRIBA lift >= CRUNCH_UP_FACTOR = 0.15,
  - para armar hace falta estar tumbado: inclinacion hombro-cadera <= ON_GROUND_ARM_MAX_TILT_DEG = 20 (y <= ON_GROUND_MAX_TILT_DEG = 40 durante la serie),
  - boca arriba (checkOnBack): rodilla NO mas de 0.45 del muslo por debajo de la cadera (BACK_KNEE_BELOW_HIP_MAX_FACTOR) y, con el torso casi horizontal (<= 30°),
    la muñeca NO mas de 0.7 del muslo por debajo del hombro (BACK_HANDS_BELOW_SHOULDER_MAX_FACTOR): con los brazos arriba la muñeca queda POR ENCIMA del hombro, no molesta.
GIF de 2 fotogramas: abajo (tumbado, brazos estirados al techo con la mancuerna) -> arriba (hombros arriba, los brazos siguen estirados y la mancuerna sube con ellos).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_weighted_crunch.py [carpeta_salida] [clave=valor ...]   (genera weighted-crunch.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t0=2, h0=8, t1=24, h1=46, thigh=127, arm0=90, arm1=100, far_arm=4,
           hand_up=0.12, bar_half=0.36, plate_w=0.085, plate_h=0.40, plate2_w=0.055, plate2_h=0.28, plate2_gap=0.13,
           fingers=1, margin=0.40, dur0=1200, dur1=1300)
# t0/t1: inclinacion del tronco (grados) abajo / arriba (la app: abajo <= 0.05 de muslo, arriba >= 0.15, armar con <= 20°); h0/h1: angulo de la cabeza (como crunch.gif)
# thigh: angulo del muslo (piernas dobladas, pies planos en el suelo, como crunch.gif)
# arm0 / arm1: angulo del brazo ESTIRADO (grados, 90 = vertical hacia el techo; >90 = algo hacia las rodillas); far_arm: grados de mas del brazo lejano (casi tapado por el cercano)
# hand_up: lo que sube el centro de la mano sobre la muñeca; bar_half: mitad del mango visible; plate_*: disco interior (ancho/alto); plate2_*: disco exterior; plate2_gap: separacion entre discos
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processCrunch / checkOnBack)
CRUNCH_UP_FACTOR = 0.15
CRUNCH_DOWN_FACTOR = 0.05
ON_GROUND_ARM_MAX_TILT_DEG = 20
ON_GROUND_MAX_TILT_DEG = 40
BACK_KNEE_BELOW_HIP_MAX_FACTOR = 0.45
BACK_HANDS_BELOW_SHOULDER_MAX_FACTOR = 0.7
BACK_HANDS_MAX_TILT_DEG = 30


# ---- pies planos con la planta hacia abajo aunque apunten a la izquierda (igual que ex_crunch.py)
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


def shin_for(thigh, drop=0.06):
    """angulo de la espinilla para que gluteo y pie queden en la misma linea de suelo (igual que ex_crunch.py)"""
    s = (-drop - L_THIGH * np.sin(np.deg2rad(thigh))) / L_SHIN
    return 180 + np.rad2deg(np.arcsin(-s))


def pose(torso, head, arm):
    tn, tf = CFG['thigh'], CFG['thigh'] - 6
    return dict(f=-1, hip=(0, 0.3), torso=torso, head=head,
                near_leg=('fk', tn, shin_for(tn), 180, 'flat'), far_leg=('fk', tf, shin_for(tf), 180, 'flat'),
                near_arm=('fk', arm, arm), far_arm=('fk', arm + CFG['far_arm'], arm + CFG['far_arm']))


FRAMES = [pose(CFG['t0'], CFG['h0'], CFG['arm0']), pose(CFG['t1'], CFG['h1'], CFG['arm1'])]


def final_J(fr):
    """el mismo J que usa render_scene (muñeco apoyado en el suelo), para dibujar la mancuerna encima de las manos"""
    J = build_side(fr)
    return shift_J(J, ground_shift(J) + fr.get('dy', 0))


JS = [final_J(f) for f in FRAMES]


# ---- MANCUERNA + MANOS (se dibujan como 'extra', encima del muñeco)
def rrect(c, w, h, r=0.02, n=5):
    """rectangulo (centro c, ancho w, alto h) con las esquinas redondeadas"""
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for a in np.linspace(a0, a0 + 90, n):
            pts.append((c[0] + cx + r * np.cos(np.deg2rad(a)), c[1] + cy + r * np.sin(np.deg2rad(a))))
    return np.array(pts)


def hand_poly(c, rx=0.135, ry=0.105):
    th = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    return np.array([(c[0] + rx * np.cos(a), c[1] + ry * np.sin(a)) for a in th])


def hand_center(J, sd):
    wr = J[sd + '_arm'][2]; sh = J[sd + '_arm'][0]
    u = (wr - sh) / np.linalg.norm(wr - sh)                    # direccion del brazo: la mano sigue la linea del brazo
    return wr + u * CFG['hand_up']


def dumbbell(J):
    C = hand_center(J, 'near')                                             # la mancuerna se agarra por el centro, justo donde estan las manos

    def draw(pen):
        c = pen.c
        # mango + discos (el mango pasa por las manos)
        pen.line([(C[0] - CFG['bar_half'] - CFG['plate2_gap'] - 0.01, C[1]), (C[0] + CFG['bar_half'] + CFG['plate2_gap'] + 0.01, C[1])], w=c.LW * 0.95)
        for s in (-1, 1):
            xi = C[0] + s * CFG['bar_half']
            xo = xi + s * CFG['plate2_gap']
            pen.paint([('p', rrect((xo, C[1]), CFG['plate2_w'], CFG['plate2_h']))], fillcol=SHORTS)
            pen.paint([('p', rrect((xi, C[1]), CFG['plate_w'], CFG['plate_h']))], fillcol=SHORTS)
            pen.line([(xi - s * 0.0, C[1] + CFG['plate_h'] * 0.28), (xi, C[1] - CFG['plate_h'] * 0.28)], w=c.LI * 0.5)
        # mano cercana ENCIMA del mango: puño cerrado en torno a la barra, con los dedos y el pulgar
        pen.paint([('p', hand_poly(C))])
        if CFG['fingers']:
            for dx in (-0.04, 0.01, 0.06):
                pen.line([(C[0] + dx, C[1] + 0.02), (C[0] + dx, C[1] - 0.07)], w=c.LI * 0.6)
    return draw, C


EX, CS = [], []
for J_ in JS:
    d, C = dumbbell(J_); EX.append([d]); CS.append(C)

# encuadre fijo para los dos fotogramas (muñeco + mancuerna)
pts = [all_points(J_) for J_ in JS]
for C in CS:
    ext = CFG['bar_half'] + CFG['plate2_gap'] + 0.25
    pts.append(np.array([C + (-ext, -0.25), C + (ext, 0.3)]))
pts = np.vstack(pts); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
BB = (x0 - 0.05, min(y0 - 0.25, 0), x1 + 0.12, y1 + 0.1)

render_scene(FRAMES, OUT + 'weighted-crunch', durations=[int(CFG['dur0']), int(CFG['dur1'])], margin=CFG['margin'], bbox_extra=BB, extras=EX)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processCrunch / checkOnBack)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


for i, (J, nm) in enumerate(zip(JS, ('abajo', 'arriba'))):
    S, H = J['S'], J['H']
    kn = J['near_leg'][1]
    thigh = float(np.linalg.norm(H - kn))
    lift = (S[1] - H[1]) / thigh                                # en la app y crece hacia abajo: (cadera.y - hombro.y) = aqui (hombro.y - cadera.y)
    tilt = float(np.degrees(np.arctan2(abs(S[1] - H[1]), abs(S[0] - H[0]))))
    kneeBelowHip = (H[1] - kn[1]) / thigh                       # app: (rodilla.y - cadera.y) / muslo
    msg = [f"{nm}: hombro sobre cadera {lift:.2f} muslo, inclinacion {tilt:.0f}°, rodilla bajo cadera {kneeBelowHip:.2f} (max {BACK_KNEE_BELOW_HIP_MAX_FACTOR})"]
    assert kneeBelowHip < BACK_KNEE_BELOW_HIP_MAX_FACTOR, 'boca arriba: la rodilla no puede quedar por debajo de la cadera'
    if i == 0:
        assert lift <= CRUNCH_DOWN_FACTOR, 'abajo: lift <= CRUNCH_DOWN_FACTOR'
        assert tilt <= ON_GROUND_ARM_MAX_TILT_DEG, 'abajo: tumbado para armar (<= 20°)'
    else:
        assert lift >= CRUNCH_UP_FACTOR, 'arriba: lift >= CRUNCH_UP_FACTOR'
        assert tilt <= ON_GROUND_MAX_TILT_DEG, 'arriba: sigue "tumbado" (<= 40°)'
    for sd in ('near', 'far'):
        sh, el, wr = J[sd + '_arm']
        elbow = ang3(sh, el, wr)
        handsBelow = (sh[1] - wr[1]) / thigh                    # app: (muñeca.y - hombro.y) / muslo (negativo = muñeca por encima del hombro)
        assert elbow >= 175, f'{sd}: brazo estirado'
        assert handsBelow < BACK_HANDS_BELOW_SHOULDER_MAX_FACTOR * 0 and (wr[1] - sh[1]) > 1.0, f'{sd}: muñeca claramente por encima del hombro (brazos al techo)'
        msg.append(f"{sd}: codo {elbow:.0f}°, muñeca sobre hombro {(wr[1]-sh[1])/thigh:.2f} muslo (la app solo bloquea si queda >= {BACK_HANDS_BELOW_SHOULDER_MAX_FACTOR} POR DEBAJO)")
    print(' | '.join(msg[:1])); print('   ' + '\n   '.join(msg[1:]))
print('OK: el weighted crunch coincide con los umbrales del contador (crunch, processCrunch)')
