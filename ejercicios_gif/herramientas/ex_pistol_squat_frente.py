"""Pistol squat (sentadilla a una pierna), vista FRONTAL: es la que EXIGE el contador de la app (processPistolSquat, counter_key "pistolsquat",
slug pistol-squat, migracion 0092). Mismo muñeco, estilo, suelo y flechas grises que el resto de GIFs de ejercicios_gif (figura.py); cabeza LISA (sin cara).
La version de perfil (ex_pistol_squat.py -> pistol-squat.gif) ENSEÑA el gesto; esta es la que ve la camara. Las dos valen.

Como lo mira la app: solo caderas y tobillos. Mide el ACORTAMIENTO de cada pierna (distancia cadera->tobillo / su largo de pie, calibrado al armar) y la
bajada de la cadera (drop, en largos de pierna):
  - ARMAR: de pie, de frente, quieto, las dos piernas parecidas (<= 30 % de diferencia),
  - ABAJO: drop >= PISTOLSQUAT_DROP_DOWN = 0.30 Y la pierna que trabaja <= PISTOLSQUAT_LEG_SHORT = 0.75 Y asimetria |rIzq - rDer| >= PISTOLSQUAT_ASYMMETRY = 0.18
    (la pierna MAS CORTA es la que trabaja; la estirada tambien se acorta por escorzo, por eso no basta "una pierna corta"),
  - ARRIBA (cuenta 1 por pierna): drop <= PISTOLSQUAT_DROP_UP = 0.12 y las DOS piernas >= PISTOLSQUAT_LEG_UP = 0.80.
Como se dibuja: el muñeco 2D no tiene profundidad, asi que la geometria sale del MISMO esqueleto de perfil (ex_pistol_squat.py: mismos parametros
shin*/thigh*/torso*/ext*): de frente la ALTURA de cada articulacion no cambia (es lo que mide el contador) y lo que apunta a la camara se ve en escorzo: la rodilla de
apoyo sube casi pegada al muslo, el tronco inclinado se acorta (figura.build_front 'tscale'), los brazos estirados se ven como puños junto a los hombros y la pierna
estirada se ve MUY corta (el tobillo queda justo bajo la cadera) con la zapatilla grande y la suela hacia la camara. Esa pierna corta, mas la bajada de la cadera,
es lo que da la asimetria que pide el contador (la pierna estirada se acorta por escorzo mas aun que la de apoyo).
GIF de 4 fotogramas: de pie con los dos pies en el suelo (flecha gris abajo) -> bajando (levanta una pierna al frente) -> abajo (cuclillas profundas sobre
una pierna, la otra estirada hacia la camara) -> subiendo (flecha gris arriba) -> (vuelve a apoyar el pie y a estar de pie).
Al final se simula la maquina de estados de processPistolSquat con la geometria dibujada: tiene que contar exactamente 1 repeticion por vuelta.
Uso: python ex_pistol_squat_frente.py [carpeta_salida] [clave=valor ...]   (genera pistol-squat-frente.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(shinU=270, shinM=257, shinB=246,        # EL MISMO esqueleto que ex_pistol_squat.py (perfil)
           thighU=270, thighM=325, thighB=20,
           torsoU=90, torsoM=70, torsoB=53,
           headU=90, headM=82, headB=74,
           extU=9, extM=6, extB=4,
           foot_ext=38, arm=7, arm_far=12,
           ext_dyM=0.14, ext_dyB=0.10, ext_x=-0.14,  # pierna estirada (apunta a la camara): tobillo apenas por debajo de la cadera y casi en el eje; zapatilla grande
           shoe_k=1.65,                              # factor de perspectiva de la zapatilla de la pierna estirada (mas cerca de la camara = mas grande)
           kx=0.05, arm_ua=0.30, arm_fa=0.22,                                 # la rodilla de apoyo se abre un poco hacia fuera (sigue la direccion del pie)
           margin=0.42, arrows=1, arrow_x=1.15, arrow_len=0.55,
           durA=1100, durB=600, durC=1200, durD=600)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (bloque PISTOLSQUAT_*)
PISTOLSQUAT_ARM_MAX_LEG_DIFF = 0.30
PISTOLSQUAT_DROP_DOWN = 0.30
PISTOLSQUAT_LEG_SHORT = 0.75
PISTOLSQUAT_ASYMMETRY = 0.18
PISTOLSQUAT_DROP_UP = 0.12
PISTOLSQUAT_LEG_UP = 0.80
PISTOLSQUAT_RECAL_DROP_MAX = 0.25
PISTOLSQUAT_RECAL_MAX_ASYM = 0.12

Y0 = 0.03                    # el tobillo de apoyo a 0.17 del suelo (zapatilla de frente: figura.front_shift)
HW, SW = 0.15, 0.34          # semi-ancho de cadera y de hombros (figura.build_front)


# ---------------------------------------------------------------- esqueleto de perfil (igual que ex_pistol_squat.py)
def hip_rel(shin, thigh):
    return -dv(shin) * L_SHIN - dv(thigh) * L_THIGH


def side_pose(st):
    shin, thigh, torso, head, ext = (CFG['shin' + st], CFG['thigh' + st], CFG['torso' + st], CFG['head' + st], CFG['ext' + st])
    return dict(f=1, ground=True, plain_head=True, hip=tuple(hip_rel(shin, thigh)), torso=torso, head=head,
                near_leg=('ik', (0.0, 0.0), 'ccw', 0), far_leg=('fk', ext, ext, ext + CFG['foot_ext']),
                near_arm=('fk', CFG['arm'], CFG['arm']), far_arm=('fk', CFG['arm_far'], CFG['arm_far']),
                near_hand=CFG['arm'], far_hand=CFG['arm_far'])


SJ = {}
for st in 'UMB':
    J = build_side(side_pose(st)); SJ[st] = shift_J(J, ground_shift(J))


# ---------------------------------------------------------------- proyeccion frontal
def P(lat, pt):
    """punto del esqueleto de perfil (x = hacia delante = hacia la camara, y = altura) con lateral 'lat' -> (x, y) de imagen. De frente la ALTURA no cambia
    (lo que mide el contador); la profundidad solo acorta lo que apunta a la camara (rodilla de apoyo, pierna estirada, brazos)."""
    return np.array([lat, pt[1] + Y0]), 1.0


def pose_front(st, ext_up):
    """pose frontal a partir del esqueleto de perfil 'st'. ext_up=False: la pierna lejana (izquierda) apoyada en el suelo (de pie con los dos pies)."""
    J = SJ[st]
    H2, fH = P(0.0, J['H']); S2, fS = P(0.0, J['S'])
    pose = dict(view='front', ground=False, hip=(0.0, float(H2[1])), torso=90, head=90, tscale=float(S2[1] - H2[1]))
    meta = {}
    hip = {'R': np.array([HW, H2[1]]), 'L': np.array([-HW, H2[1]])}
    # brazos estirados al frente (hacia la camara): de frente se ven MUY acortados (el brazo apunta al objetivo): hombro redondo y puño grande un poco por debajo
    for sd, lat in (('R', SW), ('L', -SW)):
        pose[sd + '_arm'] = ('fk', 262 if sd == 'R' else 278, 270)
        pose['fore_' + sd + '_ua'] = CFG['arm_ua']; pose['fore_' + sd + '_fa'] = CFG['arm_fa']
    # pierna de apoyo (derecha de la imagen): rodilla hacia la camara, pie plano en el suelo
    hp_, kn_, an_ = J['near_leg'][:3]
    kn2, fk = P(HW + CFG['kx'] * (0 if st == 'U' else 1), kn_); an2, fa = P(HW, an_)
    v1, v2 = kn2 - hip['R'], an2 - kn2
    pose['R_leg'] = ('fk', ang(v1), ang(v2), 1); pose['thigh_R'] = float(np.linalg.norm(v1) / L_THIGH); pose['shin_R'] = float(np.linalg.norm(v2) / L_SHIN)
    meta['R'] = (1.0, 1.15 if st != 'U' else 1.0, 1.0)
    # pierna estirada (izquierda de la imagen): recta hacia la camara
    if ext_up:
        dy = CFG['ext_dy' + st]
        an2 = np.array([CFG['ext_x'], H2[1] - dy]); kn2 = np.array([CFG['ext_x'] - 0.02, H2[1] - dy / 2])
        v1, v2 = kn2 - hip['L'], an2 - kn2
        pose['L_leg'] = ('fk', ang(v1), ang(v2), -1); pose['thigh_L'] = float(np.linalg.norm(v1) / L_THIGH); pose['shin_L'] = float(np.linalg.norm(v2) / L_SHIN)
        meta['L'] = (1.15, 1.35, CFG['shoe_k'])
    else:
        pose['L_leg'] = ('fk', 270, 270, -1)
        meta['L'] = (1.0, 1.0, 1.0)
    return pose, meta


pU, mU_ = pose_front('U', False)
pM, mM_ = pose_front('M', True)
pB, mB_ = pose_front('B', True)
frames = [pU, pM, pB, pM]
metas = [mU_, mM_, mB_, mM_]
durs = [CFG['durA'], CFG['durB'], CFG['durC'], CFG['durD']]


# ---------------------------------------------------------------- piernas por DELANTE del cuerpo (figura.draw_front pinta las piernas antes que el tronco)
def piernas_delante(J, meta):
    def f(pen):
        LI = pen.c.LI
        for sd in ('R', 'L'):
            hp, kn, an, fd = J[sd + '_leg']
            fh, fk, fa = meta[sd]
            shapes = tube(hp, kn, 0.19 * fh, 0.13 * fk, bulge=0.07, peak=0.4) + tube(kn, an, 0.13 * fk, 0.075 * fa, bulge=0.2, peak=0.3)
            th = np.linspace(0, 2 * np.pi, 32, endpoint=False)
            if sd == 'L':
                # pierna estirada hacia la camara: de frente se ve la SUELA de la zapatilla (pie en flexion), grande por la perspectiva
                fc = an + np.array([0.0, -0.04 * fa])
                shapes.append(('p', np.stack([fc[0] + 0.115 * fa * np.cos(th), fc[1] + 0.150 * fa * np.sin(th)], 1)))
                pen.paint(shapes)
                for dy_, w_ in ((0.075, 0.075), (0.0, 0.085), (-0.075, 0.075)):      # dibujo de la suela
                    pen.line([fc + np.array([-w_ * fa, dy_ * fa]), fc + np.array([w_ * fa, dy_ * fa])], w=LI * 0.9)
                continue
            fc = an + np.array([fd * 0.05 * fa, -0.10 * fa])
            shapes.append(('p', np.stack([fc[0] + 0.12 * fa * np.cos(th), fc[1] + 0.08 * fa * np.sin(th)], 1)))
            pen.paint(shapes)
            pen.line(smooth_curve([hp + (kn - hp) * 0.45, hp + (kn - hp) * 0.7, hp + (kn - hp) * 0.92]), w=LI * 0.9)
            # pantalon: mitad alta del muslo
            end = hp + (kn - hp) * 0.50
            tv = (end - hp) / (np.linalg.norm(end - hp) + 1e-9); tn = np.array([-tv[1], tv[0]])
            pts = [end + tn * s_ * 0.20 * fk for s_ in (1, -1)] + [hp + 0.21 * fh * np.array([np.cos(a_), np.sin(a_)]) for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False)]
            pen.paint([('p', cv2.convexHull(np.array(pts, np.float32)).reshape(-1, 2))], SHORTS)
            pen.line([end + tn * 0.19 * fk, end - tn * 0.19 * fk], w=LI * 0.9)
    return f


JFs = [build_front(p_) for p_ in frames]
hipsY = [J['H'][1] for J in JFs]


def flecha(bajando):
    def f(pen):
        if not CFG['arrows']:
            return
        yc = (hipsY[0] + hipsY[2]) / 2 + 0.45; h = CFG['arrow_len'] / 2
        a, b = (yc + h, yc - h) if bajando else (yc - h, yc + h)
        draw_line_arrow(pen, (CFG['arrow_x'], a), (CFG['arrow_x'], b))
    return f


extras = [[flecha(True)], [piernas_delante(JFs[1], metas[1])], [piernas_delante(JFs[2], metas[2])], [piernas_delante(JFs[3], metas[3]), flecha(False)]]
imgs = render_scene(frames, OUT + 'pistol-squat-frente', durations=durs, margin=CFG['margin'], extras=extras)


# ---------------------------------------------------------------- comprobacion contra el contador (processPistolSquat)
def medidas(J):
    """lo que ve el contador: largo de cada pierna (cadera->tobillo) y altura de la cadera (el aspecto se cancela: son cocientes de distancias en pixeles)"""
    legL = float(np.linalg.norm(J['L_leg'][0] - J['L_leg'][2])); legR = float(np.linalg.norm(J['R_leg'][0] - J['R_leg'][2]))
    return legL, legR, float(J['H'][1])


refL, refR, refY = medidas(JFs[0])
avg = (refL + refR) / 2
Ms = []
for n_, J in zip(['de pie', 'bajando', 'abajo'], JFs[:3]):
    lL, lR, hy = medidas(J)
    Ms.append(dict(rL=lL / refL, rR=lR / refR, drop=(refY - hy) / avg))
    m = Ms[-1]
    print(f"{n_:8s}: pierna izq (estirada) {m['rL']:.2f} | pierna der (apoyo) {m['rR']:.2f} | asimetria {abs(m['rL'] - m['rR']):.2f} | drop de la cadera {m['drop']:.2f}")
mU, mM, mB = Ms
mM2 = mM
assert abs(refL - refR) <= PISTOLSQUAT_ARM_MAX_LEG_DIFF * max(refL, refR), 'armar: las dos piernas parecidas'
assert abs(mU['rL'] - 1) < 1e-6 and abs(mU['rR'] - 1) < 1e-6 and abs(mU['drop']) < 1e-6, 'de pie = la referencia'
assert mB['drop'] >= PISTOLSQUAT_DROP_DOWN + 0.2, f"abajo: la cadera baja bien por encima de 0.30 ({mB['drop']:.2f})"
assert min(mB['rL'], mB['rR']) <= PISTOLSQUAT_LEG_SHORT - 0.2, 'abajo: la pierna que trabaja se acorta bien por debajo de 0.75'
assert abs(mB['rL'] - mB['rR']) >= PISTOLSQUAT_ASYMMETRY + 0.03, f"abajo: asimetria >= 0.18 con margen ({abs(mB['rL'] - mB['rR']):.2f})"
assert PISTOLSQUAT_DROP_UP < mM['drop'] < PISTOLSQUAT_DROP_DOWN, f"medio: ni abajo ni arriba (drop {mM['drop']:.2f})"
assert abs(mM['rL'] - mM['rR']) > PISTOLSQUAT_RECAL_MAX_ASYM, 'medio: no dispara la recalibracion (las dos piernas cambian IGUAL)'
# --- maquina de estados de processPistolSquat (ya armado en 'top'; 3 vueltas): 1 repeticion por vuelta
state, reps, side = 'top', 0, None
for vuelta in range(3):
    for m in (mU, mM, mB, mM2, mU):
        if state == 'top':
            if m['drop'] >= PISTOLSQUAT_DROP_DOWN and min(m['rL'], m['rR']) <= PISTOLSQUAT_LEG_SHORT and abs(m['rL'] - m['rR']) >= PISTOLSQUAT_ASYMMETRY:
                state = 'down'; side = 'left' if m['rL'] < m['rR'] else 'right'
        elif m['drop'] <= PISTOLSQUAT_DROP_UP and m['rL'] >= PISTOLSQUAT_LEG_UP and m['rR'] >= PISTOLSQUAT_LEG_UP:
            reps += 1; state = 'top'
assert reps == 3, f'el contador debe sumar 1 repeticion por vuelta ({reps} en 3 vueltas)'
print(f"OK: pistol squat de frente coincide con el contador (pistolsquat): drop {mB['drop']:.2f} (>= {PISTOLSQUAT_DROP_DOWN}), pierna de apoyo {mB['rR']:.2f} (<= {PISTOLSQUAT_LEG_SHORT}), "
      f"asimetria {abs(mB['rL'] - mB['rR']):.2f} (>= {PISTOLSQUAT_ASYMMETRY}); arriba drop 0.00 y piernas 1.00/1.00; 1 repeticion por ciclo")
