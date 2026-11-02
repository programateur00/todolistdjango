"""Fondos con peso (weighted dips) en paralelas, vista de PERFIL, mirando a la DERECHA. Misma escena, muñeco, paralelas (marco con dos postes y barra
cercana por delante del cuerpo), puños, recuadro gris "visto desde arriba" y 4 fotogramas que ex_fondos.py (fondos normales: la app usa el MISMO
contador "dip", slug weighted-dips, processDip en workout.js; con lastre solo cambian los umbrales: DIP_TUNING_LOADED). Lo unico nuevo es el LASTRE:
un CINTURON de lastre oscuro con hebilla y anilla en la cintura (igual que ex_dominadas_peso.py) del que cuelga una cadena con un DISCO de pesas,
que cuelga recto por delante de los muslos y sube y baja con el cuerpo.
Piernas y pies (peticion de Alex): rodillas dobladas a 90° (muslo casi vertical, espinilla casi horizontal hacia atras) y el PIE a 90° de la espinilla
con la planta plana, igual que el pie del crunch (figura.draw_side, pie 'libre' de ex_dominadas_commando.py).
Al final se comprueban los umbrales del contador (con y sin peso) contra la geometria dibujada (assert).
Uso: python ex_fondos_peso.py [carpeta_salida] [clave=valor ...]   (genera fondos-con-peso.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 2.2
CFG = dict(hx=0.0, far_dx=-0.05, straight=0.997, tiltA=8, tiltB=24, tiltM=15, dropB_dx=0.20, dropB_dy=0.64, midB_dy=0.98, mid_dx=0.20,
           thighA=282, shinA=192, thighB=285, shinB=195, thighM=283, shinM=193, foot=90, gap=7, post0=-1.5, post1=1.3,
           plate_rx=0.17, plate_ry=0.27, chain=0.24,
           margin=0.6, arrows=1, arrow_x=-0.8, inset=1, inset_x=2.45, inset_y=2.95, inset_s=1.0, mirror=0)
# hx: x de las manos (fijas en la barra); far_dx: la mano lejana queda un poco detras (profundidad)
# straight: fraccion del brazo estirado arriba (1 = recto del todo); tiltA/B/M: grados que el tronco se inclina hacia delante (arriba / abajo / a medio camino)
# dropB_dx/dy: abajo, posicion del hombro respecto a la muñeca (delante / encima); midB_dy / mid_dx: lo mismo a medio camino
# thigh/shin: angulos (matematicos) de muslo y espinilla en cada fotograma (rodillas dobladas hacia atras: espinilla ~ 40-55 grados de la vertical); foot: giro del pie respecto a la espinilla
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
DIP_UP_ANGLE_DEG = 155
DIP_DOWN_ANGLE_DEG = 100
DIP_MIN_SHOULDER_DROP_FACTOR = 0.30
DIP_ARM_VERTICAL_MIN_RATIO = 0.65
DIP_ARM_TILT_MAX_RATIO = 0.75
DIP_SHANK_LIFT_MIN_DEG = 40
DIP_WRIST_MAX_SHIFT = 0.8
REACH = L_UA + L_FA

# --- pie 'libre' (igual que ex_dominadas_commando.py): el talon del lado de la PLANTA tambien cuando el pie apunta a la izquierda
_limb_leg_orig = figura.limb_leg


def _limb_leg(spec, H):
    if len(spec) > 4 and spec[4] == 'libre':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        d = dv(spec[3]); p = rot(d, -90) if d[0] >= 0 else rot(d, 90)
        he = a + p * 0.10 - d * 0.07
        return H, k, a, he, he + d * 0.44
    return _limb_leg_orig(spec, H)


figura.limb_leg = _limb_leg

hx = CFG['hx']; hxf = hx + CFG['far_dx']
RIG = [('bar', BAR, CFG['post0'], CFG['post1']), ('post', CFG['post0'], 0.0, BAR + 0.0), ('post', CFG['post1'], 0.0, BAR + 0.0)]


def piernas(th, sh):
    """Piernas con las rodillas dobladas hacia atras y los pies despegados del suelo (como pide la app para armar): el muslo cuelga
    casi vertical, la espinilla se va hacia atras y abajo, los pies cruzados detras (la pierna lejana algo mas retrasada)."""
    g = CFG['gap']; ft = CFG['foot']
    return dict(near_leg=('fk', th, sh, sh + ft, 'libre'), far_leg=('fk', th - g, sh - g, sh - g + ft, 'libre'))


def pose(sh_xy, tilt, th, sh, near_elbow, far_elbow):
    """sh_xy: hombro; tilt: grados que el tronco se inclina hacia delante (90 - tilt = angulo del torso); manos fijas en las barras"""
    return dict(f=1, ground=False, sh=sh_xy, torso=90 - tilt, head=90 - tilt * 0.45,
                near_arm=('ik', (hx, BAR + 0.075), near_elbow), far_arm=('ik', (hxf, BAR + 0.075), far_elbow), **piernas(th, sh))


# ARRIBA: brazos estirados, hombro encima de las manos (casi vertical)
dyA = np.sqrt((CFG['straight'] * REACH) ** 2 - 0.0 ** 2)
A = pose((hx + 0.02, BAR + 0.075 + dyA), CFG['tiltA'], CFG['thighA'], CFG['shinA'], 'cw', 'cw')
# ABAJO: codos doblados y echados hacia atras, hombro bajo y algo por delante de las manos
B = pose((hx + CFG['dropB_dx'], BAR + 0.075 + CFG['dropB_dy']), CFG['tiltB'], CFG['thighB'], CFG['shinB'], 'cw', 'cw')
# A MEDIO CAMINO (bajando o subiendo)
M = pose((hx + CFG['mid_dx'] * 0.6, BAR + 0.075 + CFG['midB_dy']), CFG['tiltM'], CFG['thighM'], CFG['shinM'], 'cw', 'cw')

# comprobacion de que el codo se dobla hacia ATRAS (el codo queda por detras del hombro y de la muñeca)
for p_ in (A, B, M):
    J_ = build_side(p_)
    assert J_['near_arm'][1][0] < max(J_['S'][0], hx) + 1e-6, 'el codo debe quedar detras (hacia atras), cambia ccw/cw'


def cara(J):
    """Nariz, ojo y oreja (la cabeza de figura.py solo lleva un bultito): se ve hacia donde mira."""
    hd, face = J['hd'], J['face']
    v = (hd - J['S']) / (np.linalg.norm(hd - J['S']) + 1e-9); hc = hd + v * 0.035
    fa = np.arctan2(face[1], face[0]); d_ = lambda a: np.array([np.cos(a), np.sin(a)])
    up = np.array([-face[1], face[0]]); up = up if up[1] > 0 else -up
    base = [hc + 0.265 * d_(fa + dd) for dd in (-0.17, 0.0, 0.17)]
    tip = hc + 0.318 * d_(fa - 0.05)
    ojo = hc + 0.14 * d_(fa) + up * 0.07
    oreja = hc - 0.04 * d_(fa) - up * 0.02

    def f(pen):
        pen.paint([('p', np.array([base[0], tip, base[2]]))])
        pen.paint([('c', ojo, 0.022)])
        pen.line(smooth_curve([oreja + up * 0.06, oreja - d_(fa) * 0.04, oreja - up * 0.06]), w=pen.c.LI * 0.9)
    return f


def manos(pose_):
    """Manos agarrando las barras: la barra pasa POR DELANTE del puño y los nudillos asoman por encima (como en commando)."""
    J = build_side(pose_)
    ex = [lambda pen: pen.line([(CFG['post0'], BAR), (CFG['post1'], BAR)], w=pen.c.LW * 1.3)]   # la barra CERCANA pasa por delante del cuerpo (la lejana queda tapada)

    def puño(pen, w_):
        c = pen.c
        pen.paint([('c', (w_[0], BAR + 0.045), 0.085)])
        pen.line([(w_[0] - 0.16, BAR), (w_[0] + 0.16, BAR)], w=c.LW * 1.3)
        for dx in (-0.04, 0.0, 0.04):
            pen.line([(w_[0] + dx, BAR + 0.05), (w_[0] + dx, BAR + 0.105)], w=c.LI * 0.8)
    for sd in ('far', 'near'):
        w_ = J[sd + '_arm'][2]
        ex.append(lambda pen, w_=w_: puño(pen, w_))
    return ex


def flechas(bajando, ymid):
    """Flecha gris detras del cuerpo: el cuerpo baja / sube (las manos no se mueven)."""
    def f(pen):
        if not CFG['arrows']:
            return
        x = CFG['arrow_x']
        a, b = (ymid + 0.40, ymid - 0.40) if bajando else (ymid - 0.40, ymid + 0.40)
        draw_line_arrow(pen, (x, a), (x, b))
    return f


def vista_cenital(estado):
    """Recuadro gris 'visto desde arriba': las dos lineas son las DOS barras paralelas (de perfil se tapan una a otra), los puntos las manos
    y el circulo la cabeza, entre las barras. estado 0 = arriba (cabeza centrada) / 1 = abajo (cabeza algo mas adelantada, circulo punteado = arriba)."""
    k_ = CFG['inset_s']; cx, cy, hw, hh = CFG['inset_x'], CFG['inset_y'], 0.95 * k_, 0.72 * k_
    gap = 0.34 * k_

    def f(pen):
        if not CFG['inset']:
            return
        pen.line([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh), (cx - hw, cy - hh)], w=pen.c.LI * 0.8, col=FLOOR)
        for sg in (1, -1):
            pen.line([(cx - hw + 0.12, cy + sg * gap), (cx + hw - 0.12, cy + sg * gap)], w=pen.c.LW * 0.9)
        # hombros (linea entre las barras) y cabeza (circulo); abajo la cabeza queda mas adelante (a la derecha)
        hxs = cx + (0.0 if estado == 0 else 0.18 * k_) - 0.05 * k_
        pen.line([(hxs - 0.0, cy - gap * 0.78), (hxs - 0.0, cy + gap * 0.78)], w=pen.c.LW * 0.9)
        pen.paint([('c', (hxs + 0.12 * k_, cy), 0.14 * k_)])
        if estado == 1:
            th = np.linspace(0, 2 * np.pi, 48); r = 0.14 * k_
            for a0 in range(0, 48, 6):
                seg = [(cx - 0.05 * k_ + 0.12 * k_ + r * np.cos(t), cy + r * np.sin(t)) for t in th[a0:a0 + 3]]
                pen.line(seg, w=pen.c.LI * 0.8, col=GREY_ARROW)
        for sg in (1, -1):
            pen.paint([('c', (cx - 0.05 * k_ - 0.0, cy + sg * gap), 0.05 * k_)])
    return f



# ---------------------------------------------------------------- LASTRE (cinturon + cadena + disco)
METAL = (104, 104, 104)
SHINE = (232, 232, 232)
RF0 = [(-0.14, .13), (0.0, .21), (0.12, .30), (0.26, .32), (0.46, .24), (0.70, .20), (1.0, .235), (1.12, .245)]   # perfil del torso (figura.draw_side)
RB0 = [(-0.14, .13), (0.0, .19), (0.12, .26), (0.30, .25), (0.52, .20), (0.76, .18), (1.0, .225), (1.12, .235)]
wf = lambda s: np.interp(s, [p[0] for p in RF0], [p[1] for p in RF0]) * 1.22 * 1.06
wb = lambda s: np.interp(s, [p[0] for p in RB0], [p[1] for p in RB0]) * 1.18 * 1.06


def lastre(pose_):
    """Cinturon de lastre (banda en la cintura + hebilla + anilla) y, colgando de la anilla, cadena + disco visto algo de lado."""
    J = build_side(pose_); S, H, bel = J['S'], J['H'], J['bel']
    ax = H - S; L = np.linalg.norm(ax); u = ax / L
    cs = lambda s: S + u * L * s
    s0, s1 = 0.80, 0.98
    ring = cs(s1 - 0.02) + bel * (wf(s1) + 0.005)
    rx, ry = CFG['plate_rx'], CFG['plate_ry']
    ctr = np.array([ring[0], ring[1] - CFG['chain'] - ry])

    def belt(pen):
        c = pen.c
        poly = np.array([cs(s0) + bel * (wf(s0) + 0.02), cs(s1) + bel * (wf(s1) + 0.02),
                         cs(s1) - bel * (wb(s1) + 0.02), cs(s0) - bel * (wb(s0) + 0.02)], float)
        pen.paint([('p', poly)], METAL)
        b0 = cs(0.89) + bel * (wf(0.89) - 0.03)
        pen.line([b0 + u * 0.07, b0 - u * 0.07, b0 - u * 0.07 - bel * 0.09, b0 + u * 0.07 - bel * 0.09, b0 + u * 0.07], w=c.LI * 0.9, col=SHINE)   # hebilla
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
        pen.paint([('p', el(1.0))], METAL)                                                    # disco
        pen.line(np.vstack([el(0.74), el(0.74)[:1]]), w=c.LI * 0.8, col=SHINE)                # ranura del borde
        pen.paint([('p', el(0.28))])                                                          # agujero central
        pen.circ_px(ctr, c.LI * 1.4, INK)
        pen.circ_px(ring, c.LI * 1.9, INK); pen.circ_px(ring, c.LI * 0.8, WHITE)
    return [belt, disco]


def brazo_delante(pose_):
    """El brazo cercano va POR DELANTE del cinturon (el cinturon se pinta despues del muñeco): se repinta igual que figura.draw_side."""
    J = build_side(pose_); s_, e_, w_ = J['near_arm']; bel = J['bel']

    def f(pen):
        c = pen.c
        pen.paint([('c', s_, 0.145)] + tube(s_, e_, 0.125, 0.095, bulge=0.17, peak=0.42) + tube(e_, w_, 0.095, 0.085, bulge=0.13, peak=0.3))
        n1 = pen.side_normal('nearua', s_, e_, bel); n2 = pen.side_normal('nearfa', e_, w_, bel)
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.22 + n1 * 0.045, s_ + (e_ - s_) * 0.50 + n1 * 0.062, s_ + (e_ - s_) * 0.80 + n1 * 0.03]))
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.12 - n1 * 0.07, s_ + (e_ - s_) * 0.45 - n1 * 0.075, s_ + (e_ - s_) * 0.75 - n1 * 0.045]))
        pen.line(smooth_curve([s_ + n1 * 0.10, s_ + (e_ - s_) * 0.18 + n1 * 0.095, s_ + (e_ - s_) * 0.28 + n1 * 0.06]), w=c.LI * 0.9)
        pen.line(smooth_curve([e_ + (w_ - e_) * 0.12 + n2 * 0.035, e_ + (w_ - e_) * 0.42 + n2 * 0.045, e_ + (w_ - e_) * 0.78 + n2 * 0.02]))
    return f


JA, JB, JM = build_side(A), build_side(B), build_side(M)
yA, yB, yM = JA['S'][1], JB['S'][1], JM['S'][1]
ex = lambda p, extra: [cara(build_side(p))] + lastre(p) + [brazo_delante(p)] + manos(p) + extra
inset_box = (CFG['inset_x'] - 1.0, CFG['inset_y'] - 0.8, CFG['inset_x'] + 1.0, CFG['inset_y'] + 0.8) if CFG['inset'] else None
render_scene([A, M, B, M], OUT + 'fondos-con-peso', props=RIG, durations=[1200, 700, 1300, 700], margin=CFG['margin'], bbox_extra=inset_box,
             extras=[ex(A, [vista_cenital(0)]), ex(M, [flechas(True, (yA + yB) / 2), vista_cenital(0)]),
                     ex(B, [vista_cenital(1)]), ex(M, [flechas(False, (yA + yB) / 2), vista_cenital(0)])])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def codo(J, sd):
    sh, e, w_ = J[sd + '_arm']; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def espinilla(J, sd):
    """grados de la espinilla (rodilla->tobillo) respecto a 'recto hacia abajo' (igual que shankDeg en processDip)"""
    hp, k, a = J[sd + '_leg'][:3]
    dx, dy = a[0] - k[0], k[1] - a[1]
    return float(np.degrees(np.arctan2(abs(dx), dy)))


def suelo(J):
    """punto mas bajo de las piernas (tobillo / talon / punta del pie): debe quedar sobre el suelo (y=0)"""
    return min(min(J[sd + '_leg'][2][1], J[sd + '_leg'][3][1], J[sd + '_leg'][4][1]) for sd in ('near', 'far'))


torso = float(np.linalg.norm(JA['S'] - JA['H']))
for nombre, J in (('arriba', JA), ('a medio camino', JM), ('abajo', JB)):
    s, e, w_ = J['near_arm']; arm = np.linalg.norm(s - e) + np.linalg.norm(e - w_)
    print(f"{nombre:15s}: codo {codo(J,'near'):.0f}° | brazo dy/largo {(s[1]-w_[1])/arm:.2f} dx/largo {abs(s[0]-w_[0])/arm:.2f} | "
          f"hombro a {(J['S'][1]-yB)/torso:+.2f} troncos sobre el punto bajo | espinillas {espinilla(J,'near'):.0f}°/{espinilla(J,'far'):.0f}° | pie mas bajo a y={suelo(J):.2f}")
drop = (yA - yB) / torso
print(f"hombro baja {drop:.2f} troncos (minimo {DIP_MIN_SHOULDER_DROP_FACTOR}); muñeca fija (desplazamiento 0)")
sA, eA, wA = JA['near_arm']; armA = np.linalg.norm(sA - eA) + np.linalg.norm(eA - wA)
assert codo(JA, 'near') >= DIP_UP_ANGLE_DEG and codo(JA, 'far') >= DIP_UP_ANGLE_DEG, 'arriba: el codo debe estar casi recto'
assert (sA[1] - wA[1]) >= DIP_ARM_VERTICAL_MIN_RATIO * armA and abs(sA[0] - wA[0]) <= DIP_ARM_TILT_MAX_RATIO * armA, 'arriba: el brazo debe ser vertical'
assert codo(JB, 'near') < DIP_DOWN_ANGLE_DEG and codo(JB, 'far') < DIP_DOWN_ANGLE_DEG, 'abajo: el codo debe bajar de 100'
assert drop >= DIP_MIN_SHOULDER_DROP_FACTOR + 0.05, 'el hombro debe bajar con margen'
for J in (JA, JM, JB):
    assert espinilla(J, 'near') >= DIP_SHANK_LIFT_MIN_DEG and espinilla(J, 'far') >= DIP_SHANK_LIFT_MIN_DEG, 'rodillas dobladas hacia atras (pies levantados)'
    assert suelo(J) > 0.15, 'los pies no deben tocar el suelo'
print('OK: arriba, abajo y a medio camino coinciden con los umbrales del contador')

def angulo_rodilla(J, sd):
    hp, k, a = J[sd + '_leg'][:3]; u = hp - k; v = a - k
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def angulo_pie(J, sd):
    hp, k, a, he, to = J[sd + '_leg']; u = k - a; v = to - he
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


for J in (JA, JM, JB):
    for sd in ('near', 'far'):
        assert abs(angulo_rodilla(J, sd) - 90) <= 4, ('rodilla a 90', angulo_rodilla(J, sd))
        assert abs(angulo_pie(J, sd) - 90) <= 4, ('pie a 90 de la espinilla', angulo_pie(J, sd))
print('rodillas y pies a 90 grados en los 3 estados; umbrales con peso (codo >=145 arriba, <=108 abajo, hombro >=0.22) incluidos en los de sin peso')
