"""Sentadillas con peso (weighted squat) = sentadilla GOBLET: de pie, de PERFIL, mirando a la DERECHA, con una MANCUERNA agarrada en vertical
pegada al pecho (las dos manos la sujetan por la cabeza de arriba, codos hacia abajo). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara),
igual que weighted-crunch.gif / crunch.gif. Misma escena, muñeco, suelo y mancuerna (estilo de ex_weighted_crunch.py) que el resto de ejercicios_gif.
Como lo cuenta la app (workout.js: processSquat, counter "squat", slug weighted-squat, migracion 0020; MISMO contador que la sentadilla sin peso, no se toca workout.js):
  - angulo de la rodilla (cadera-rodilla-tobillo) de la pierna mejor vista: ARRIBA >= SQUAT_UP_ANGLE_DEG = 160, ABAJO <= SQUAT_DOWN_ANGLE_DEG = 100,
  - para armar hace falta estar DE PIE de verdad visto de perfil (isStandingSideView): cadera->tobillo >= 65° sobre la horizontal y tronco (hombro->cadera) >= 55°.
Tecnica de la sentadilla goblet: pies a la anchura de los hombros y planos en el suelo (los talones no se levantan), tronco erguido (se inclina hacia delante solo lo justo
al bajar), cadera hacia atras y abajo, rodillas sobre las puntas de los pies (no mucho mas alla), muslos al menos paralelos al suelo, peso pegado al pecho con los codos abajo
(entre las rodillas) y subir empujando el suelo hasta estirar las piernas.
GIF de 4 fotogramas (como fondos-con-peso.gif): de pie -> bajando -> abajo (muslos paralelos) -> subiendo, con una flecha gris que indica el sentido.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_sentadilla_peso.py [carpeta_salida] [clave=valor ...]   (genera sentadillas-con-peso.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
AY = 0.14   # altura del tobillo con la zapatilla plana apoyada en el suelo (igual que ground_shift de figura.py: talon a y=0.04)
CFG = dict(far_dx=-0.06,
           thA=268, shA=272, thM=326, shM=256, thB=357, shB=245,      # muslo (cadera->rodilla) y espinilla (rodilla->tobillo) en cada fotograma (angulos matematicos)
           tA=90, tM=73, tB=57, hA=90, hM=82, hB=74,                  # inclinacion del tronco y de la cabeza
           wx=0.42, wy=0.30, wy_M=0.26, wy_B=0.14,                               # muñeca: delante del pecho (wx, en el sentido del vientre) y por debajo del hombro (wy de pie / wy_M a medio camino / wy_B abajo, a lo largo del tronco)
           far_wx=0.38, ax_follow=0.90, up=0.20,
           bar_half=0.27, gap=0.12, plate_d=0.50, plate_t=0.11, plate2_d=0.38, plate2_t=0.07, fist=1,
           arrows=1, arrow_x=-1.05, margin=0.28, d0=1200, dM=700, dB=1300)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processSquat / isStandingSideView)
SQUAT_UP_ANGLE_DEG = 160
SQUAT_DOWN_ANGLE_DEG = 100
ARM_STANDING_LEG_MIN_TILT_DEG = 65
ARM_STANDING_TORSO_MIN_TILT_DEG = 55

ANK = np.array([0.0, AY]); ANK_F = np.array([CFG['far_dx'], AY])


def hip_for(th, sh):
    """cadera que deja el TOBILLO cercano exactamente en ANK (pie plano, fijo en el suelo) para esos angulos de muslo / espinilla"""
    knee = ANK - dv(sh) * L_SHIN
    return knee - dv(th) * L_THIGH


def pose(th, sh, t, h, wy):
    H = hip_for(th, sh); S = H + dv(t)
    bel = dv(t - 90); down = (H - S) / np.linalg.norm(H - S)
    wn = S + bel * CFG['wx'] + down * wy
    wf = S + bel * CFG['far_wx'] + down * (wy - 0.02)
    return dict(f=1, ground=False, hip=tuple(H), torso=t, head=h,
                near_leg=('ik', tuple(ANK), 'ccw', 0), far_leg=('ik', tuple(ANK_F), 'ccw', 0),
                near_arm=('ik', tuple(wn), 'cw'), far_arm=('ik', tuple(wf), 'cw'))


A = pose(CFG['thA'], CFG['shA'], CFG['tA'], CFG['hA'], CFG['wy'])
M = pose(CFG['thM'], CFG['shM'], CFG['tM'], CFG['hM'], CFG['wy_M'])
B = pose(CFG['thB'], CFG['shB'], CFG['tB'], CFG['hB'], CFG['wy_B'])


# ---- la rodilla va hacia DELANTE (derecha) y el pie queda plano: se comprueba aqui mismo
def J_of(p):
    return build_side(p)


# ---------------------------------------------------------------- MANCUERNA + MANOS (se dibujan como 'extra', encima del muñeco)
def rrect(c, w, h, r=0.02, n=5, rot_deg=0.0):
    """rectangulo (centro c, ancho w, alto h) con las esquinas redondeadas, girado rot_deg alrededor de su centro"""
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for a in np.linspace(a0, a0 + 90, n):
            pts.append((cx + r * np.cos(np.deg2rad(a)), cy + r * np.sin(np.deg2rad(a))))
    pts = np.array(pts)
    c_, s_ = np.cos(np.deg2rad(rot_deg)), np.sin(np.deg2rad(rot_deg))
    pts = np.stack([pts[:, 0] * c_ - pts[:, 1] * s_, pts[:, 0] * s_ + pts[:, 1] * c_], 1)
    return pts + np.asarray(c, float)


def hand_poly(c, rx=0.135, ry=0.105, rot_deg=0.0):
    th = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    pts = np.stack([rx * np.cos(th), ry * np.sin(th)], 1)
    c_, s_ = np.cos(np.deg2rad(rot_deg)), np.sin(np.deg2rad(rot_deg))
    pts = np.stack([pts[:, 0] * c_ - pts[:, 1] * s_, pts[:, 0] * s_ + pts[:, 1] * c_], 1)
    return pts + np.asarray(c, float)


def eje(p):
    """direccion (hacia arriba) del eje de la mancuerna: vertical de pie, algo inclinada con el tronco al bajar (apoyada en el pecho)"""
    return 90 - (90 - p['torso']) * CFG['ax_follow']


def mano_centro(J):
    s_, e_, w_ = J['near_arm']; u = (w_ - e_) / np.linalg.norm(w_ - e_)
    return w_ + u * 0.07


def mancuerna(p, J):
    ang = eje(p); ax = dv(ang); C = mano_centro(J)
    P1 = C + ax * CFG['up']                                       # disco interior de arriba (justo encima de las manos)
    P0 = P1 + ax * CFG['gap'] * 0.9                               # disco exterior de arriba
    P2 = P1 - ax * 2 * CFG['bar_half']                            # disco interior de abajo
    P3 = P2 - ax * CFG['gap'] * 0.9                               # disco exterior de abajo
    rot = ang - 90

    def draw(pen):
        c = pen.c
        pen.line([P0 + ax * 0.02, P3 - ax * 0.02], w=c.LW * 0.95)                          # mango (pasa por las manos)
        for Pi, Po in ((P1, P0), (P2, P3)):
            pen.paint([('p', rrect(Po, CFG['plate2_d'], CFG['plate2_t'], rot_deg=rot))], fillcol=SHORTS)
            pen.paint([('p', rrect(Pi, CFG['plate_d'], CFG['plate_t'], rot_deg=rot))], fillcol=SHORTS)
    return draw, C


def brazo_delante(J):
    """el brazo cercano va POR DELANTE de la mancuerna: se repinta igual que figura.draw_side (y como en ex_fondos_peso.py)"""
    s_, e_, w_ = J['near_arm']; bel = J['bel']

    def f(pen):
        c = pen.c
        pen.paint([('c', s_, 0.145)] + tube(s_, e_, 0.125, 0.095, bulge=0.17, peak=0.42) + tube(e_, w_, 0.095, 0.085, bulge=0.13, peak=0.3))
        n1 = pen.side_normal('nearua', s_, e_, bel); n2 = pen.side_normal('nearfa', e_, w_, bel)
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.22 + n1 * 0.045, s_ + (e_ - s_) * 0.50 + n1 * 0.062, s_ + (e_ - s_) * 0.80 + n1 * 0.03]))
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.12 - n1 * 0.07, s_ + (e_ - s_) * 0.45 - n1 * 0.075, s_ + (e_ - s_) * 0.75 - n1 * 0.045]))
        pen.line(smooth_curve([s_ + n1 * 0.10, s_ + (e_ - s_) * 0.18 + n1 * 0.095, s_ + (e_ - s_) * 0.28 + n1 * 0.06]), w=c.LI * 0.9)
        pen.line(smooth_curve([e_ + (w_ - e_) * 0.12 + n2 * 0.035, e_ + (w_ - e_) * 0.42 + n2 * 0.045, e_ + (w_ - e_) * 0.78 + n2 * 0.02]))
    return f


def puño(p, J):
    """mano cercana ENCIMA del mango: puño cerrado en torno a la mancuerna, con los dedos (como weighted-crunch.gif)"""
    C = mano_centro(J); ax = dv(eje(p)); nx = np.array([-ax[1], ax[0]])
    rot = eje(p) - 90

    def f(pen):
        c = pen.c
        pen.paint([('p', hand_poly(C, rot_deg=rot))])
        if CFG['fist']:
            for dx in (-0.055, 0.0, 0.055):
                pen.line([C + nx * dx + ax * 0.03, C + nx * dx - ax * 0.065], w=c.LI * 0.6)
    return f


def flechas(bajando, ymid):
    def f(pen):
        if not CFG['arrows']:
            return
        x = CFG['arrow_x']
        a, b = (ymid + 0.45, ymid - 0.45) if bajando else (ymid - 0.45, ymid + 0.45)
        draw_line_arrow(pen, (x, a), (x, b))
    return f


def extras(p, J, extra=()):
    d, _ = mancuerna(p, J)
    return [d, brazo_delante(J), puño(p, J)] + list(extra)


JA, JM, JB = J_of(A), J_of(M), J_of(B)
yA, yB = JA['H'][1], JB['H'][1]
ymid = (yA + yB) / 2
FR = [A, M, B, M]
EX = [extras(A, JA), extras(M, JM, [flechas(True, ymid)]), extras(B, JB), extras(M, JM, [flechas(False, ymid)])]

# encuadre fijo (muñeco + mancuerna + flecha)
pts = [all_points(J_) for J_ in (JA, JM, JB)]
pts.append(np.array([(CFG['arrow_x'] - 0.2, 0.0), (1.4, yA + 1.4)]))
pts = np.vstack(pts); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
BB = (x0 - 0.05, min(y0 - 0.25, 0), x1 + 0.1, y1 + 0.40)

render_scene(FR, OUT + 'sentadillas-con-peso', durations=[int(CFG['d0']), int(CFG['dM']), int(CFG['dB']), int(CFG['dM'])],
             margin=CFG['margin'], bbox_extra=BB, extras=EX)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def tilt(a, b):
    d = b - a
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


def suelo(J):
    return min(min(J[sd + '_leg'][3][1], J[sd + '_leg'][4][1]) for sd in ('near', 'far'))


names = ('arriba', 'a medio camino', 'abajo')
for nm, J in zip(names, (JA, JM, JB)):
    S, H = J['S'], J['H']
    hp, kn, an, he, to = J['near_leg']
    kA = ang3(hp, kn, an)
    kF = ang3(J['far_leg'][0], J['far_leg'][1], J['far_leg'][2])
    print(f"{nm:15s}: rodilla {kA:.0f}° (lejana {kF:.0f}°) | cadera->tobillo {tilt(hp, an):.0f}° | tronco {tilt(S, H):.0f}° | "
          f"rodilla x={kn[0]:+.2f} (punta del pie x={to[0]:+.2f}) | cadera y={H[1]:.2f} | hombro x={S[0]:+.2f} | pie mas bajo y={suelo(J):.3f}")
    # el pie esta plano y quieto en todos los fotogramas, la rodilla va hacia delante y el hombro no se va de los pies (equilibrio)
    assert abs(suelo(J) - suelo(JA)) < 1e-6, 'los pies deben quedar apoyados siempre a la misma altura'
    assert abs(to[1] - he[1]) < 1e-6 and to[0] > he[0], 'pie plano apuntando hacia delante'
    assert kn[0] > hp[0] and kn[0] > an[0] - 0.05, 'la rodilla va hacia delante'
    assert kn[0] - to[0] < 0.10, 'la rodilla no debe pasar mucho de la punta del pie'
    assert abs(S[0] - an[0]) < 0.5, 'el peso queda sobre los pies'
    for sd in ('near', 'far'):
        s_, e_, w_ = J[sd + '_arm']
        assert e_[1] < w_[1] - 0.05, f'{nm} {sd}: codo por debajo de la muñeca (codos hacia abajo)'

assert ang3(JA['near_leg'][0], JA['near_leg'][1], JA['near_leg'][2]) >= SQUAT_UP_ANGLE_DEG + 10, 'arriba: la rodilla casi estirada (>= 160 con margen)'
assert ang3(JB['near_leg'][0], JB['near_leg'][1], JB['near_leg'][2]) <= SQUAT_DOWN_ANGLE_DEG - 20, 'abajo: la rodilla bien doblada (<= 100 con margen)'
assert SQUAT_DOWN_ANGLE_DEG < ang3(JM['near_leg'][0], JM['near_leg'][1], JM['near_leg'][2]) < SQUAT_UP_ANGLE_DEG, 'a medio camino: ni arriba ni abajo del todo'
assert tilt(JA['near_leg'][0], JA['near_leg'][2]) >= ARM_STANDING_LEG_MIN_TILT_DEG and tilt(JA['S'], JA['H']) >= ARM_STANDING_TORSO_MIN_TILT_DEG, 'arriba: de pie de verdad (isStandingSideView)'
assert JB['near_leg'][1][1] <= JB['H'][1] + 0.1, 'abajo: muslo al menos paralelo al suelo (rodilla a la altura de la cadera o mas abajo)'
print('OK: arriba, a medio camino y abajo coinciden con los umbrales del contador (sentadilla, processSquat)')
