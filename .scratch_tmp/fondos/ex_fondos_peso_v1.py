"""Fondos con peso (weighted dips) en paralelas, vista de PERFIL (de lado a la camara), mirando a la DERECHA.
La app usa el MISMO contador "dip" que los fondos normales (slug weighted-dips, counter_key dip, processDip en workout.js) y pide
colocar el movil DE LADO, encuadrando hombro, codo y muñeca del lado que mira a la camara. Por eso el GIF va de perfil (como
commando / crunch) y no de frente (como los GIFs de barra de dominadas).
Mismo lastre que ex_dominadas_peso.py (la serie "con peso"): CINTURON de lastre oscuro con hebilla en la cintura, del que cuelga una
cadena con un DISCO de pesas. Aqui el disco cuelga por delante de los muslos (las piernas van dobladas hacia atras) y sube y baja
con el cuerpo, siempre en vertical.
Postura (la que arma el contador, DIP_*):
  - ARRIBA: brazos rectos y verticales apoyados en las paralelas (codo >= DIP_UP_ANGLE_DEG; con lastre 145), cuerpo algo inclinado
    hacia delante, rodillas dobladas y pies levantados (espinilla >= DIP_SHANK_LIFT_MIN_DEG = 40 grados de la vertical),
  - ABAJO: codos doblados hacia atras (<= DIP_DOWN_ANGLE_DEG; con lastre 108; aqui ~88) y el hombro baja >= DIP_MIN_SHOULDER_DROP_FACTOR
    (0.30 troncos; con lastre 0.22) -> es lo que valida la repeticion; las manos NO se mueven (DIP_WRIST_MAX_SHIFT).
Al final se comprueban esos umbrales contra la geometria dibujada (assert).
Uso: python ex_fondos_peso.py [carpeta_salida] [clave=valor ...]   (genera fondos-con-peso.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
YB = 2.0                                  # altura de las paralelas (las manos)
CFG = dict(elbowB=88, dxB=0.10, tA=84, tB=64, headA=88, headB=70, thighA=262, shinA=182, thighB=254, shinB=176,
           plate_rx=0.19, plate_ry=0.30, chain=0.28, margin=0.55, hand=1)
# elbowB: angulo del codo abajo (grados); dxB: cuanto se adelanta el hombro abajo respecto a la muñeca; tA/tB: inclinacion del torso (90 = vertical)
# plate_rx/ry: semiejes del disco visto algo de lado (elipse); chain: largo de la cadena entre la anilla y el disco; hand: 1 = dibuja la mano sobre la barra
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (DIP_TUNING_LOADED = con peso; DIP_TUNING_NORMAL = sin peso)
DIP_UP_ANGLE_LOADED, DIP_DOWN_ANGLE_LOADED = 145, 108
DIP_UP_ANGLE, DIP_DOWN_ANGLE = 155, 100
DIP_MIN_DROP_LOADED, DIP_MIN_DROP = 0.22, 0.30
DIP_SHANK_LIFT_MIN_DEG = 40
DIP_ARM_VERTICAL_MIN_RATIO, DIP_ARM_TILT_MAX_RATIO = 0.65, 0.75
L1, L2 = L_UA, L_FA
METAL = (104, 104, 104)
SHINE = (232, 232, 232)

HX = 0.0                                  # x de las manos (apoyo en la barra)
HAND_Y = YB + 0.07                        # la palma queda justo encima de la barra
# arriba: brazo recto y vertical (ik a una muñeca justo debajo del hombro)
shA = (HX, HAND_Y + (L1 + L2) * 0.999)
# abajo: el hombro baja hasta que el codo forme 'elbowB' grados; el hombro queda dxB por delante de la muñeca
d = np.sqrt(L1 ** 2 + L2 ** 2 - 2 * L1 * L2 * np.cos(np.deg2rad(CFG['elbowB'])))
shB = (HX + CFG['dxB'], HAND_Y + np.sqrt(d ** 2 - CFG['dxB'] ** 2))

legs = lambda th, sh: dict(near_leg=('fk', th, sh, 250), far_leg=('fk', th + 4, sh + 4, 250))


def pose(sh, torso, head, arm_bend, th, sh_):
    return dict(f=1, ground=False, sh=sh, torso=torso, head=head,
                near_arm=('ik', (HX, HAND_Y), arm_bend), far_arm=('ik', (HX + 0.03, HAND_Y), arm_bend), **legs(th, sh_))


A = pose(shA, CFG['tA'], CFG['headA'], 'cw', CFG['thighA'], CFG['shinA'])
B = pose(shB, CFG['tB'], CFG['headB'], 'cw', CFG['thighB'], CFG['shinB'])

# paralelas vistas de lado: la barra (horizontal) sobre un poste con pie
BARX0, BARX1 = -0.75, 0.60
RIG = [('bar', YB, BARX0, BARX1), ('post', -0.55, 0.0, YB), ('floorbar', -1.15, 0.0, 0.05, 0.0)]

# perfil del torso (igual que figura.draw_side) para pintar el cinturon pegado al cuerpo
RF0 = [(-0.14, .13), (0.0, .21), (0.12, .30), (0.26, .32), (0.46, .24), (0.70, .20), (1.0, .235), (1.12, .245)]
RB0 = [(-0.14, .13), (0.0, .19), (0.12, .26), (0.30, .25), (0.52, .20), (0.76, .18), (1.0, .225), (1.12, .235)]
wf = lambda s: np.interp(s, [p[0] for p in RF0], [p[1] for p in RF0]) * 1.22 * 1.06
wb = lambda s: np.interp(s, [p[0] for p in RB0], [p[1] for p in RB0]) * 1.18 * 1.06


def mano(pose_):
    """Mano apoyada en la barra vista de lado: la palma encima, los dedos rodeando la barra por delante."""
    J = build_side(pose_); out = []
    if not CFG['hand']:
        return out
    for sd in ('far', 'near'):
        w = J[sd + '_arm'][2]

        def f(pen, w=w):
            c = pen.c
            pen.line([(w[0] - 0.09, YB + 0.035), (w[0] + 0.17, YB + 0.035)], w=c.LW * 1.3)       # barra por delante de la palma
            pen.line(smooth_curve([(w[0] + 0.03, YB + 0.075), (w[0] + 0.10, YB + 0.085), (w[0] + 0.15, YB + 0.045)]), w=c.LI * 1.0)   # dedos que rodean la barra
        out.append(f)
    return out


def lastre(pose_):
    """Cinturon de lastre (banda en la cintura + hebilla + anilla) y, colgando de la anilla, cadena + disco vertical."""
    J = build_side(pose_); S, H, bel = J['S'], J['H'], J['bel']
    ax = H - S; L = np.linalg.norm(ax); u = ax / L
    cs = lambda s: S + u * L * s
    s0, s1 = 0.80, 0.98
    ring = cs(s1 - 0.02) + bel * (wf(s1) + 0.005)                    # anilla delante, abajo del cinturon
    rx, ry = CFG['plate_rx'], CFG['plate_ry']
    ctr = np.array([ring[0], ring[1] - CFG['chain'] - ry])           # centro del disco (cuelga recto bajo la anilla)

    def belt(pen):
        c = pen.c
        poly = np.array([cs(s0) + bel * (wf(s0) + 0.02), cs(s1) + bel * (wf(s1) + 0.02),
                         cs(s1) - bel * (wb(s1) + 0.02), cs(s0) - bel * (wb(s0) + 0.02)], float)
        pen.paint([('p', poly)], METAL)
        sm = 0.89                                                    # hebilla en el frente
        b0 = cs(sm) + bel * (wf(sm) - 0.03)
        hb = [b0 + u * 0.07, b0 - u * 0.07, b0 - u * 0.07 - bel * 0.09, b0 + u * 0.07 - bel * 0.09, b0 + u * 0.07]
        pen.line(hb, w=c.LI * 0.9, col=SHINE)
        pen.circ_px(ring, c.LI * 1.9, SHINE); pen.circ_px(ring, c.LI * 0.9, METAL)

    def chain(pen, p, q):
        c = pen.c; p = np.asarray(p, float); q = np.asarray(q, float); Ln = np.linalg.norm(q - p)
        pen.line([p, q], w=c.LI * 0.7)
        for t in np.linspace(0, 1, max(2, int(Ln / 0.05) + 1)):
            pen.circ_px(p + (q - p) * t, c.LI * 1.05, INK)

    def disco(pen):
        c = pen.c
        chain(pen, ring, ctr)
        th = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        el = lambda k: np.stack([ctr[0] + k * rx * np.cos(th), ctr[1] + k * ry * np.sin(th)], 1)
        pen.paint([('p', el(1.0))], METAL)                           # disco
        pen.line(np.vstack([el(0.74), el(0.74)[:1]]), w=c.LI * 0.8, col=SHINE)   # ranura del borde
        pen.paint([('p', np.stack([ctr[0] + 0.28 * rx * np.cos(th), ctr[1] + 0.28 * ry * np.sin(th)], 1))])   # agujero central
        pen.circ_px(ctr, c.LI * 1.4, INK)                            # extremo de la cadena
        pen.circ_px(ring, c.LI * 1.9, INK); pen.circ_px(ring, c.LI * 0.8, WHITE)
    return [belt, disco], dict(ring=ring, ctr=ctr)


def brazo_delante(pose_):
    """El brazo cercano a la camara va POR DELANTE del cinturon (el cinturon se pinta despues del muñeco): se repinta igual que
    figura.draw_side (hombro, musculos y antebrazo)."""
    J = build_side(pose_); s_, e_, w_ = J['near_arm']; bel = J['bel']

    def f(pen):
        c = pen.c
        shapes = [('c', s_, 0.145)] + tube(s_, e_, 0.125, 0.095, bulge=0.17, peak=0.42) + tube(e_, w_, 0.095, 0.085, bulge=0.13, peak=0.3)
        pen.paint(shapes)
        n1 = pen.side_normal('nearua', s_, e_, bel); n2 = pen.side_normal('nearfa', e_, w_, bel)
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.22 + n1 * 0.045, s_ + (e_ - s_) * 0.50 + n1 * 0.062, s_ + (e_ - s_) * 0.80 + n1 * 0.03]))
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.12 - n1 * 0.07, s_ + (e_ - s_) * 0.45 - n1 * 0.075, s_ + (e_ - s_) * 0.75 - n1 * 0.045]))
        pen.line(smooth_curve([s_ + n1 * 0.10, s_ + (e_ - s_) * 0.18 + n1 * 0.095, s_ + (e_ - s_) * 0.28 + n1 * 0.06]), w=c.LI * 0.9)
        pen.line(smooth_curve([e_ + (w_ - e_) * 0.12 + n2 * 0.035, e_ + (w_ - e_) * 0.42 + n2 * 0.045, e_ + (w_ - e_) * 0.78 + n2 * 0.02]))
    return f


lA, infoA = lastre(A); lB, infoB = lastre(B)
render_scene([A, B], OUT + 'fondos-con-peso', props=RIG, durations=[1200, 1200], margin=CFG['margin'], y_floor=0.0,
             extras=[lA + [brazo_delante(A)] + mano(A), lB + [brazo_delante(B)] + mano(B)])


# ---------------------------------------------------------------- comprobacion contra el contador
def elbow(J):
    s, e, w = J['near_arm']
    v1, v2 = s - e, w - e
    return float(np.rad2deg(np.arccos(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))))


JA, JB = build_side(A), build_side(B)
eA, eB = elbow(JA), elbow(JB)
torso = np.linalg.norm(JA['S'] - JA['H'])
drop = (JA['S'][1] - JB['S'][1]) / torso
wrist_shift = np.linalg.norm(JA['near_arm'][2] - JB['near_arm'][2])


def shank_dev(J):
    hp, kn, an, he, to = J['near_leg']
    v = an - kn
    return float(np.rad2deg(np.arccos(abs(v[1]) / np.linalg.norm(v))))


def arm_ratios(J):
    s, e, w = J['near_arm']; Ln = L1 + L2
    return abs(s[1] - w[1]) / Ln, abs(w[0] - s[0]) / Ln


print('codo arriba %.1f (>= %d con peso / %d)  codo abajo %.1f (<= %d con peso / %d)' % (eA, DIP_UP_ANGLE_LOADED, DIP_UP_ANGLE, eB, DIP_DOWN_ANGLE_LOADED, DIP_DOWN_ANGLE))
print('bajada del hombro %.2f troncos (>= %.2f con peso / %.2f)  muñeca desplazada %.3f' % (drop, DIP_MIN_DROP_LOADED, DIP_MIN_DROP, wrist_shift))
print('espinilla de la vertical: arriba %.0f  abajo %.0f (>= %d = pies levantados)' % (shank_dev(JA), shank_dev(JB), DIP_SHANK_LIFT_MIN_DEG))
vr, tr = arm_ratios(JA)
print('brazo arriba: vertical %.2f (>= %.2f)  inclinacion %.2f (<= %.2f)' % (vr, DIP_ARM_VERTICAL_MIN_RATIO, tr, DIP_ARM_TILT_MAX_RATIO))
assert eA >= DIP_UP_ANGLE, eA
assert eB <= DIP_DOWN_ANGLE, eB
assert drop >= DIP_MIN_DROP, drop
assert wrist_shift < 0.05, wrist_shift
assert shank_dev(JA) >= DIP_SHANK_LIFT_MIN_DEG and shank_dev(JB) >= DIP_SHANK_LIFT_MIN_DEG
assert vr >= DIP_ARM_VERTICAL_MIN_RATIO and tr <= DIP_ARM_TILT_MAX_RATIO
print('OK: cumple los umbrales del contador (con y sin peso)')
