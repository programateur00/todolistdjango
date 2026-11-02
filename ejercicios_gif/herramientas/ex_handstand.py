"""Handstand (pino aguantado), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo, pared y reloj gris que flexiones-en-pino / l-sit-hold. SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app (workout.js: checkHandstandPosture, counter "handstand", slug handstand, mode=timed): AGUANTE cronometrado en el PINO,
boca abajo con las manos en el suelo; la postura es la misma con o sin apoyo en la pared (valen vista de frente o de lado):
  - cadera POR ENCIMA de los hombros (margen HANDSTAND_MARGIN_FACTOR = 0.08 anchos de hombro),
  - codos y muñecas por DEBAJO de la cadera, y las muñecas por debajo de los hombros (manos en el suelo aguantando el peso),
  - tobillos (y rodillas) claramente por ENCIMA de la cadera (HANDSTAND_ANKLE_ABOVE_HIP_FACTOR = 0.6, HANDSTAND_KNEE_ABOVE_HIP_FACTOR = 0.3 anchos de hombro),
  - brazos estirados, cuerpo recto (hombro-cadera-tobillo en linea), cabeza entre los brazos, manos fijas; las puntas de los pies tocan la pared
    (pino con la BARRIGA hacia la pared; wall=0 la quita y los pies quedan en el aire).
GIF de 2 fotogramas (el mismo pino aguantado con el reloj gris avanzando), igual que dead-hang / l-sit-hold.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_handstand.py [carpeta_salida] [clave=valor ...]   (genera handstand.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elb=178, lean=0, tilt=4, headd=0, far_dx=-0.07, far_tilt=0, foot=105, footF=105, wall=1, wall_gap=0.07, margin=0.12,
           clock=1, clock_dx=0.95, clock_y=1.55, clock_r=0.27, fingers=1, dur=1400)
# elb: angulo del codo (grados, brazos estirados: la app pide >= 140 en la flexion en pino); lean: grados que el brazo se inclina hacia atras (0 = hombro justo sobre la muñeca)
# tilt: inclinacion (grados) del cuerpo recto hacia la pared (los pies la tocan); headd: grados que la cabeza gira respecto al tronco (0 = alineada)
# far_dx: mano lejana, algo detras; far_tilt: grados que la pierna lejana va menos inclinada hacia la pared (0 = tapada por la cercana, limpio)
# foot / footF: angulo del pie cercano / lejano (105 = puntas estiradas); wall=0 quita la pared; wall_gap: separacion pared-puntas
# clock_dx / clock_y / clock_r: posicion (a la derecha de las manos) y radio del reloj gris; dur: ms por fotograma
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
HANDSTAND_MARGIN_FACTOR = 0.08
HANDSTAND_ANKLE_ABOVE_HIP_FACTOR = 0.6
HANDSTAND_KNEE_ABOVE_HIP_FACTOR = 0.3
SHOULDER_W = 0.68               # ancho de hombros del muñeco visto de frente (figura.build_front: 2 * 0.34), la unidad de los factores de arriba

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo
LEG = L_THIGH + L_SHIN          # pierna recta
BODY = 1.0 + LEG                # hombro -> tobillo con el cuerpo recto (torso 1 + pierna)
W = np.array([0.0, WY])         # muñeca cercana (FIJA)


def elbow_len(deg):
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


# ---- PIES: figura.py dibuja zapatillas planas (de pie); en el pino los pies van con las puntas estiradas hacia arriba, asi que se sustituyen
# por un pie en punta que sigue la linea de la pierna (mismo parche que ex_flexiones_pino.py).
_limb_leg = figura.limb_leg


def limb_leg_pino(spec, H):
    hp, k, a, he, to = _limb_leg(spec, H)
    d = dv(spec[3]); p = rot(d, -90)
    to = a + d * 0.40 - p * 0.03
    return hp, k, a, to - d * 0.44, to


PIE_UV = np.array([(-0.03, -0.075), (0.07, -0.085), (0.20, -0.085), (0.33, -0.075), (0.44, -0.058), (0.52, -0.03), (0.545, 0.012),
                   (0.50, 0.052), (0.41, 0.075), (0.29, 0.090), (0.16, 0.112), (0.05, 0.140), (-0.04, 0.140), (-0.085, 0.105), (-0.06, 0.07)])


def foot_poly_pino(an, he, to):
    d = (to - he) / (np.linalg.norm(to - he) + 1e-9); p = rot(d, -90)
    return np.array([an + u * d + v * p for u, v in PIE_UV])


figura.limb_leg = limb_leg_pino
figura.foot_poly = foot_poly_pino
foot_poly = foot_poly_pino


def foot_left(foot):
    hp, k, a, he, to = limb_leg_pino(('fk', 90, 90, foot), np.zeros(2))
    return float(foot_poly(a, he, to)[:, 0].min() - a[0])


# ---- el pino: brazos estirados con el hombro sobre la muñeca; cuerpo recto inclinado `tilt` grados hacia la pared (izquierda)
S = W + elbow_len(CFG['elb']) * dv(90 + CFG['lean'])
tau = CFG['tilt']
up = dv(90 + tau)
H = S + up                      # cadera a 1 torso por encima del hombro
ANK = S + BODY * up
leg = 90 + tau
X_OFF = foot_left(CFG['foot'])
X_WALL = ANK[0] + X_OFF - CFG['wall_gap']


def elbow_back(S_, e):
    xl = S_[0] + (W[0] - S_[0]) * (S_[1] - e[1]) / (S_[1] - W[1])
    return e[0] <= xl + 1e-6


def pose():
    p = dict(f=1, ground=False, hip=tuple(H), torso=-90 + tau, head=-90 + tau + CFG['headd'],
             near_leg=('fk', leg, leg, CFG['foot']), far_leg=('fk', leg - CFG['far_tilt'], leg - CFG['far_tilt'], CFG['footF']))
    HX, HXF = W[0], W[0] + CFG['far_dx']
    for bend in ('cw', 'ccw'):
        e, _ = ik2(S, W, L_UA, L_FA, bend)
        if elbow_back(S, e):
            break
    p['near_arm'] = ('ik', (HX, WY), bend); p['far_arm'] = ('ik', (HXF, WY), bend)
    p['near_hand'] = HAND; p['far_hand'] = HAND
    return p


P = pose()
J = build_side(P)


def dedos(pen):
    """rayitas de los dedos sobre la mano apoyada (se lee la palma plana en el suelo)"""
    if not CFG['fingers']:
        return
    w_, tip = J['near_arm'][2], J['near_handtip']
    for k_ in (0.12, 0.20):
        x = tip[0] - k_
        pen.line([(x, w_[1] + 0.045), (x, w_[1] + 0.085)], w=pen.c.LI * 0.8)


def pared(pen):
    """la pared: raya gris vertical del suelo hasta arriba del todo (mismo gris y grosor que el suelo)"""
    if not CFG['wall']:
        return
    x = pen.c.C((X_WALL, 0))[0]; fy = pen.c.C((0, -0.055))[1]
    cv2.line(pen.img, (int(round(x)), 0), (int(round(x)), int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)


_draw_side = figura.draw_side


def draw_side_con_pared(pen, J_, props_back=None):
    pared(pen)                                           # la pared va DETRAS del muñeco
    _draw_side(pen, J_, props_back)


figura.draw_side = draw_side_con_pared


def reloj(hand_deg):
    """reloj gris al lado del pino (aguante cronometrado): esfera + manecilla larga + corta fija (igual que l-sit-hold)"""
    def draw(pen):
        if not CFG['clock']:
            return
        c = np.array([W[0] + CFG['clock_dx'], CFG['clock_y']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


cx = W[0] + CFG['clock_dx']
bb = (X_WALL - 0.1, -0.1, cx + CFG['clock_r'] + 0.2, ANK[1] + 0.62)
imgs = render_scene([P, P], OUT + 'handstand', ground_all=False, durations=[int(CFG['dur']), int(CFG['dur'])],
                    margin=CFG['margin'], bbox_extra=bb,
                    extras=[[dedos, reloj(90)], [dedos, reloj(-10)]])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (checkHandstandPosture)
def codo(J_, sd):
    sh, e, w_ = J_[sd + '_arm']; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def foot_min_x(J_):
    xs = []
    for s_ in ('near', 'far'):
        hp, k, a, he, to = J_[s_ + '_leg']
        xs.append(foot_poly(a, he, to)[:, 0].min())
    return min(xs)


MARGIN = HANDSTAND_MARGIN_FACTOR * SHOULDER_W
hip, sh = J['H'], J['S']
ankle, knee = J['near_leg'][2], J['near_leg'][1]
kneeF, ankleF = J['far_leg'][1], J['far_leg'][2]
wr, el = J['near_arm'][2], J['near_arm'][1]
print(f"pino: codo {codo(J,'near'):.0f}° | cadera sobre hombro {hip[1]-sh[1]:.2f} (mín {MARGIN:.2f}) | tobillo sobre cadera {ankle[1]-hip[1]:.2f} "
      f"(mín {HANDSTAND_ANKLE_ABOVE_HIP_FACTOR*SHOULDER_W:.2f}) | rodilla sobre cadera {knee[1]-hip[1]:.2f} (mín {HANDSTAND_KNEE_ABOVE_HIP_FACTOR*SHOULDER_W:.2f}) | "
      f"codo bajo cadera {hip[1]-el[1]:.2f} muñeca bajo cadera {hip[1]-wr[1]:.2f} muñeca bajo hombro {sh[1]-wr[1]:.2f} | "
      f"hombro-cadera-tobillo {ang3(sh, hip, ankle):.0f}° | rodilla {ang3(hip, knee, ankle):.0f}° | pie más a la izq. x={foot_min_x(J):.2f} (pared {X_WALL+CFG['wall_gap']:.2f})")
assert hip[1] > sh[1] + MARGIN, 'la cadera debe quedar por encima de los hombros (invertida/o)'
for sd in ('near', 'far'):
    s_, e_, w_ = J[sd + '_arm']
    assert e_[1] < hip[1] - MARGIN and w_[1] < hip[1] - MARGIN, 'codos y muñecas por debajo de la cadera'
    assert w_[1] < sh[1] - MARGIN, 'muñecas por debajo de los hombros'
    assert codo(J, sd) >= 170, 'brazos estirados'
assert ankle[1] > hip[1] + HANDSTAND_ANKLE_ABOVE_HIP_FACTOR * SHOULDER_W and ankleF[1] > hip[1] + HANDSTAND_ANKLE_ABOVE_HIP_FACTOR * SHOULDER_W, 'tobillos claramente por encima de la cadera'
assert knee[1] > hip[1] + HANDSTAND_KNEE_ABOVE_HIP_FACTOR * SHOULDER_W and kneeF[1] > hip[1] + HANDSTAND_KNEE_ABOVE_HIP_FACTOR * SHOULDER_W, 'rodillas por encima de la cadera'
assert ang3(hip, knee, ankle) > 178, 'piernas rectas'
assert ang3(sh, hip, ankle) > 175, 'cuerpo recto (hombro-cadera-tobillo en linea)'
assert elbow_back(J['S'], J['near_arm'][1]) or abs(codo(J, 'near') - 180) < 12, 'codo detras de la recta hombro-muñeca'
assert J['hd'][1] - 0.27 > 0.3, 'la cabeza queda lejos del suelo (entre los brazos, no apoyada)'
if CFG['wall']:
    assert abs(foot_min_x(J) - (X_WALL + CFG['wall_gap'])) < 1e-6 and J['H'][0] > X_WALL, 'las puntas de los pies tocan la pared'
    assert J['hd'][0] - 0.3 > X_WALL, 'la cabeza no atraviesa la pared'
print('OK: el pino coincide con los umbrales del contador (handstand, checkHandstandPosture)')
