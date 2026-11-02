"""Crow Pose (cuervo: aguante sobre las manos con los brazos casi estirados y las rodillas junto a la axila), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y reloj gris que handstand / flexiones-en-pino / l-sit-hold. SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app (workout.js: checkFrogStandPosture, counter "frogstand", slug crow-pose, mode=timed; comparte contador con frog-stand, pero es OTRO ejercicio):
AGUANTE cronometrado con las manos en el suelo, las rodillas apoyadas en los brazos y los pies en el aire:
  - muñeca POR DEBAJO de la cadera (0.25 de escala) y del hombro (0.15)  [escala = max(ancho de hombros, 0.75 * largo de tronco)],
  - pies despegados: tobillo >= 0.55 de escala por ENCIMA de la muñeca, y a >= 30% del camino de la muñeca a la cadera,
  - tobillo como mucho 1.5 de escala por DEBAJO de la rodilla (pies recogidos, no colgando),
  - rodilla >= 0.2 de escala por ENCIMA de la muñeca, rodilla doblada (cadera-rodilla-tobillo <= 125°),
  - cabeza levantada (la nariz >= 0.25 de escala por encima de las manos: no apoya la cabeza en el suelo).
CROW POSE: brazos casi ESTIRADOS (~160° en el dibujo), cadera MAS ALTA que en el frog stand, las rodillas suben hasta la parte de atras del brazo, junto a la axila,
las espinillas cuelgan hacia atras y los pies quedan bajo la cadera; cabeza adelantada y baja, mirando al suelo por delante de las manos.
GIF de 2 fotogramas (la misma pose aguantada con el reloj gris avanzando), igual que dead-hang / l-sit-hold / handstand.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_crow_pose.py [carpeta_salida] [clave=valor ...]   (genera crow-pose.gif + PNG de cada fotograma)
"""
import sys, os, inspect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BASE = dict(foot_extra=18, far_thigh=4, far_shin=7, far_dx=-0.07, far_arm=5, clock=1, clock_y=1.55, clock_r=0.27, fingers=1, margin=0.2, dur=1400)
PRESETS = {
    # fa: angulo del antebrazo (muñeca -> codo; 90 = vertical, <90 = codo algo por delante de la muñeca); elb: angulo del codo (grados)
    # t: angulo del tronco (cadera -> hombro; -90 = tronco vertical con la cabeza abajo); hipang: cuanto se pliega el muslo contra el tronco (grados)
    # knee: angulo de la rodilla (grados, 180 = pierna recta); head: angulo (absoluto) del cuello hacia la cabeza (60 = mira al frente algo hacia abajo)
    # foot_extra: grados que la punta del pie sigue girando mas alla de la espinilla (punta estirada); far_*: separacion de la pierna / brazo lejanos (casi tapados)
    # clock_x: distancia del reloj gris a las manos; clock_y / clock_r: altura y radio del reloj
    'crow': dict(name='crow-pose', label='Crow Pose', fa=78, elb=160, t=-40, hipang=17, knee=70, head=20, clock_x=1.75),
}
args = [a for a in sys.argv[2:]]
OVR = {'crow': {}, '': {}}
for a in args:
    k, v = a.split('=')
    who, _, key = k.partition('.')
    if not key:
        who, key = '', k
    OVR[who][key] = float(v)

# mismos umbrales que workout.js (checkFrogStandPosture)
FROGSTAND_WRIST_BELOW_HIP_FACTOR = 0.25
FROGSTAND_WRIST_BELOW_SHOULDER_FACTOR = 0.15
FROGSTAND_FEET_ABOVE_HANDS_FACTOR = 0.55
FROGSTAND_KNEE_ABOVE_HANDS_FACTOR = 0.2
FROGSTAND_KNEE_MAX_ANGLE_DEG = 125
FROGSTAND_FEET_FRACTION = 0.30
FROGSTAND_ANKLE_BELOW_KNEE_MAX = 1.5
FROGSTAND_HEAD_ABOVE_HANDS_MIN = 0.25

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo (igual que handstand)
W = np.array([0.0, WY])         # muñeca cercana (FIJA)
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo

# ---- PIES: figura.py dibuja zapatillas planas (de pie); aqui los pies van con la punta estirada siguiendo la espinilla (mismo parche que ex_handstand.py).
_limb_leg = figura.limb_leg


def limb_leg_punta(spec, H):
    hp, k, a, he, to = _limb_leg(spec, H)
    d = dv(spec[3]); p = rot(d, -90)
    to = a + d * 0.40 - p * 0.03
    return hp, k, a, to - d * 0.44, to


PIE_UV = np.array([(-0.03, -0.075), (0.07, -0.085), (0.20, -0.085), (0.33, -0.075), (0.44, -0.058), (0.52, -0.03), (0.545, 0.012),
                   (0.50, 0.052), (0.41, 0.075), (0.29, 0.090), (0.16, 0.112), (0.05, 0.140), (-0.04, 0.140), (-0.085, 0.105), (-0.06, 0.07)])


def foot_poly_punta(an, he, to):
    d = (to - he) / (np.linalg.norm(to - he) + 1e-9); p = rot(d, -90)
    return np.array([an + u * d + v * p for u, v in PIE_UV])


figura.limb_leg = limb_leg_punta
figura.foot_poly = foot_poly_punta
foot_poly = foot_poly_punta

# ---- ORDEN DE DIBUJO: aqui la rodilla cercana descansa FUERA del brazo (entre la camara y el brazo), asi que la pierna cercana se pinta
# DESPUES del brazo cercano (figura.draw_side pinta pierna -> pantalon -> brazo). Se parchea una copia de su codigo, solo en este script.
_src = inspect.getsource(figura.draw_side)
_old = "draw_leg('near'); shorts('near', True); draw_arm('near')"
assert _old in _src, 'figura.draw_side cambio: revisa el parche del orden de dibujo'
exec(_src.replace(_old, "draw_arm('near'); draw_leg('near'); shorts('near', True)"), figura.__dict__)


def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def seg_dist(p, a, b):
    ab = b - a; s = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return float(np.linalg.norm(p - (a + s * ab)))


def build(key):
    C = dict(BASE); C.update(PRESETS[key]); C.update(OVR['']); C.update(OVR[key])
    # ---- brazo: antebrazo desde la muñeca fija, codo con el angulo pedido, hombro por DELANTE del codo
    E = W + L_FA * dv(C['fa'])
    us = (C['fa'] + 180) + C['elb']                       # codo -> hombro
    S = E + L_UA * dv(us)
    # ---- tronco y piernas: cadera a 1 torso del hombro, muslo plegado `hipang` contra el tronco, rodilla con el angulo pedido
    t = C['t']; H = S - dv(t)
    thigh = t - C['hipang']                               # cadera -> rodilla (por debajo de la linea del tronco = lado de la barriga)
    K = H + L_THIGH * dv(thigh)
    shin = (thigh + 180) + C['knee']                      # rodilla -> tobillo: el pie va hacia atras
    foot = shin + C['foot_extra']
    P = dict(f=1, ground=False, sh=tuple(S), torso=t, head=C['head'],
             near_arm=('fk', us + 180, C['fa'] + 180),
             near_leg=('fk', thigh, shin, foot),
             far_leg=('fk', thigh + C['far_thigh'], shin + C['far_shin'], foot + C['far_shin']))
    # brazo lejano: mismo hombro, muñeca algo detras (casi tapado por el cercano)
    for bend in ('cw', 'ccw'):
        e2, _ = ik2(S, W + np.array([C['far_dx'], 0]), L_UA, L_FA, bend)
        if np.linalg.norm(e2 - E) < 0.35:
            break
    P['far_arm'] = ('ik', (W[0] + C['far_dx'], WY), bend)
    P['near_hand'] = HAND; P['far_hand'] = HAND
    return C, P


def dedos(C):
    def draw(pen):
        if not C['fingers']:
            return
        w_, tip = DJ['near_arm'][2], DJ['near_handtip']
        for k_ in (0.12, 0.20):
            x = tip[0] - k_
            pen.line([(x, w_[1] + 0.045), (x, w_[1] + 0.085)], w=pen.c.LI * 0.8)
    return draw


def reloj(C, hand_deg):
    """reloj gris al lado (aguante cronometrado): esfera + manecilla larga + corta fija (igual que handstand / l-sit-hold)"""
    def draw(pen):
        if not C['clock']:
            return
        c = np.array([W[0] + C['clock_x'], C['clock_y']]); r = C['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(a), np.sin(a)]) for a in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


def check(key, C, J):
    """umbrales del contador contra lo dibujado (todo en unidades del torso, y hacia ARRIBA; la app usa y hacia abajo, aqui ya invertido)"""
    S, H, hd = J['S'], J['H'], J['hd']
    scale = 0.75 * np.linalg.norm(S - H)                  # de perfil los hombros se solapan: manda 0.75 * tronco
    wr, el = J['near_arm'][2], J['near_arm'][1]
    out = []
    assert (H[1] - wr[1]) >= FROGSTAND_WRIST_BELOW_HIP_FACTOR * scale, 'muñeca por debajo de la cadera'
    assert (S[1] - wr[1]) >= FROGSTAND_WRIST_BELOW_SHOULDER_FACTOR * scale, 'muñeca por debajo del hombro'
    assert (hd[1] - 0.15 - wr[1]) / scale >= FROGSTAND_HEAD_ABOVE_HANDS_MIN, 'la cabeza (la nariz, ~0.15 bajo el centro) por encima de las manos'
    for sd in ('near', 'far'):
        hp, k, a, he, to = J[sd + '_leg']
        feet = (a[1] - wr[1]) / scale; knees = (k[1] - wr[1]) / scale
        frac = (a[1] - wr[1]) / (H[1] - wr[1]); abk = (k[1] - a[1]) / scale; kang = ang3(hp, k, a)
        assert feet >= FROGSTAND_FEET_ABOVE_HANDS_FACTOR, f'{sd}: pies despegados'
        assert frac >= FROGSTAND_FEET_FRACTION, f'{sd}: tobillo a >=30% del camino muñeca-cadera'
        assert abk <= FROGSTAND_ANKLE_BELOW_KNEE_MAX, f'{sd}: pies recogidos (no colgando bajo la rodilla)'
        assert knees >= FROGSTAND_KNEE_ABOVE_HANDS_FACTOR, f'{sd}: rodilla por encima de la muñeca'
        assert kang <= FROGSTAND_KNEE_MAX_ANGLE_DEG, f'{sd}: rodilla doblada'
        assert foot_poly(a, he, to)[:, 1].min() > -0.03, f'{sd}: el pie no atraviesa el suelo'
        out.append(f"{sd}: pies {feet:.2f} (min {FROGSTAND_FEET_ABOVE_HANDS_FACTOR}) fraccion {frac:.2f} (min {FROGSTAND_FEET_FRACTION}) "
                   f"tobillo bajo rodilla {abk:.2f} (max {FROGSTAND_ANKLE_BELOW_KNEE_MAX}) rodillas {knees:.2f} (min {FROGSTAND_KNEE_ABOVE_HANDS_FACTOR}) ang.rodilla {kang:.0f}° (max {FROGSTAND_KNEE_MAX_ANGLE_DEG})")
    # la rodilla cercana descansa sobre el brazo (toca la parte de atras del brazo)
    kn = J['near_leg'][1]
    dk = min(seg_dist(kn, wr, el), seg_dist(kn, el, J['S']))
    assert 0.05 <= dk <= 0.26, f'la rodilla debe apoyarse en el brazo (distancia {dk:.2f})'
    assert figura.ground_shift(J) <= 0.02, 'nada por debajo del suelo'
    print(f"{C['label']}: codo {ang3(J['S'], el, wr):.0f}° | muñeca bajo cadera {(H[1]-wr[1])/scale:.2f} (min {FROGSTAND_WRIST_BELOW_HIP_FACTOR}) bajo hombro {(S[1]-wr[1])/scale:.2f} (min {FROGSTAND_WRIST_BELOW_SHOULDER_FACTOR}) | "
          f"cabeza sobre manos {(hd[1]-0.15-wr[1])/scale:.2f} (min {FROGSTAND_HEAD_ABOVE_HANDS_MIN}) | rodilla-brazo {dk:.2f}\n   " + "\n   ".join(out))
    print(f"OK: {C['label']} coincide con los umbrales del contador (frogstand, checkFrogStandPosture)")


for key in ('crow',):
    C, P = build(key)
    J = build_side(P); DJ = J
    check(key, C, J)
    bb = (-1.15, -0.1, W[0] + C['clock_x'] + C['clock_r'] + 0.2, max(J['hd'][1] + 0.4, C['clock_y'] + C['clock_r'] + 0.1))
    render_scene([P, P], OUT + C['name'], ground_all=False, durations=[int(C['dur']), int(C['dur'])], margin=C['margin'], bbox_extra=bb,
                 extras=[[dedos(C), reloj(C, 90)], [dedos(C), reloj(C, -10)]])
