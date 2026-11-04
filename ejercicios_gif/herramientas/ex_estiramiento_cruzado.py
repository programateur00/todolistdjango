"""Estiramiento cruzado de brazo (cross-body shoulder stretch), DE FRENTE. Mismo muñeco, suelo, flechas y reloj grises que el resto de GIFs
de ejercicios_gif (figura.py). SIN cara (sin nariz, ojo ni oreja: draw_front solo dibuja un ovalo liso).

Tecnica (Planfit, Fitbod, The Prehab Guys): de pie, un brazo ESTIRADO cruzando el pecho a la altura del hombro (recto, sin doblar el codo) y la otra
mano lo agarra por encima del codo (parte alta del brazo) tirando de el hacia el pecho. Se nota en la parte de atras del hombro. Se aguanta
unos 30 s y se repite del otro lado.

Es DE FRENTE a proposito: es la vista que exige el contador de la app (counter_key="armcrossstretch", checkStandbyPosture + checkArmCrossStretch en
workout.js, migracion 0031, modo timed). Paso 1 = "standby" (de pie, brazos sueltos a los lados), paso 2 = el estiramiento; cada lado es una serie
aparte y entre lados se vuelve a standby (closeActivePostureSet). Las comprobaciones del final usan esos mismos umbrales (STRETCH_*).

Es un AGUANTE (isometrico), no un movimiento: como plank.gif, un fotograma corto de standby y despues el estiramiento quieto con el reloj gris
(manecilla a las 12 y luego avanzada). Por defecto 3 fotogramas, solo el brazo derecho; `sides=2` añade el aguante del brazo izquierdo (5 fotogramas,
sin fotograma intermedio de «cruzando»). `clock=0` quita el reloj.
Uso: python ex_estiramiento_cruzado.py [carpeta_salida] [clave=valor ...]   (genera arm-cross-stretch.gif + PNG de cada fotograma;
usar una carpeta temporal, no ejercicios_gif)
Parametros: ext_ang (angulo del brazo estirado, 184 = casi horizontal), grab_t (donde agarra la mano, fraccion del brazo desde el hombro, 0 = hombro,
1 = muñeca), swing_ang (brazo a medio camino), clock_*, arr_*, margin, sides (1 o 2), dur*.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(ext_ang=184.0, swing_ang=220.0, grab_t=0.45, grab_dy=0.0, arrows=1, clock=1, sides=1, clock_dx=1.55, clock_dy=0.62, clock_r=0.27,
           arr_r=1.62, arr_a0=236.0, arr_a1=194.0, fingers=1, margin=0.30, durS=800, durX=600, durH=1500, hip_y=2.0)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (STRETCH_*)
MIN_VIS = 0.4
STANDBY_ELBOW_MIN_DEG = 150
STANDBY_WRIST_BELOW_SHOULDER_FACTOR = 0.15
ARM_CROSS_MIN_ELBOW_DEG = 90
CROSS_MIN_FRACTION = 0.5
WRIST_HEIGHT_MAX_FACTOR = 3.2
GRAB_MAX_FACTOR = 2.4

STAND = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268))
ARMS_DOWN = dict(R_arm=('fk', 281, 272), L_arm=('fk', 259, 268))
SW = 0.34                                       # mitad del ancho de hombros (figura.build_front)
SHR = np.array([SW, 3.0 + (CFG['hip_y'] - 2.0)])  # hombro derecho de la imagen


def arm_point(shoulder, ang, t):
    """punto a lo largo del brazo ESTIRADO (t = fraccion del brazo entero desde el hombro)"""
    return np.asarray(shoulder, float) + dv(ang) * (L_UA + L_FA) * t


def pose(side, kind):
    """side='R' estira el brazo derecho de la imagen (cruza hacia la izquierda), 'L' el izquierdo (espejo). kind: 'standby'|'swing'|'hold'"""
    d = dict(view='front', hip=(0, CFG['hip_y']), torso=90, head=90, **STAND)
    if kind == 'standby':
        return dict(d, **ARMS_DOWN)
    mir = (lambda a: a) if side == 'R' else (lambda a: 180 - a)
    ext, oth = (side + '_arm'), (('L' if side == 'R' else 'R') + '_arm')
    if kind == 'swing':
        a = CFG['swing_ang']
        out = dict(d, **ARMS_DOWN); out[ext] = ('fk', mir(a), mir(a))
        return out
    a = CFG['ext_ang']
    sh = SHR if side == 'R' else SHR * np.array([-1, 1])
    g = arm_point(sh, mir(a), CFG['grab_t']) + np.array([0, CFG['grab_dy']])
    out = dict(d); out[ext] = ('fk', mir(a), mir(a))
    out[oth] = ('ik', tuple(g), 'cw' if side == 'R' else 'ccw')     # el que agarra: codo hacia abajo, antebrazo cruzado hacia arriba
    return out


SEQ = [('R', 'standby'), ('R', 'hold'), ('R', 'hold')] + ([('L', 'hold'), ('L', 'hold')] if CFG['sides'] >= 2 else [])
FRAMES = [pose(s, k) for s, k in SEQ]


def final_J(fr):
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


# ---------------------------------------------------------------- extras: flecha de giro, reloj
def flecha(J, side):
    """flecha curva gris alrededor del hombro que estira, siguiendo el recorrido de la muñeca (de abajo hacia el otro lado del pecho)"""
    def draw(pen):
        if not CFG['arrows']:
            return
        sh = J[side + '_arm'][0]
        if side == 'R':
            draw_arrow(pen, sh, CFG['arr_r'], CFG['arr_a0'], CFG['arr_a1'])
        else:
            draw_arrow(pen, sh, CFG['arr_r'], 180 - CFG['arr_a0'], 180 - CFG['arr_a1'])
    return draw


def brazo_encima(J, side):
    """repinta por ENCIMA el brazo que agarra: draw_front pinta siempre primero el derecho y luego el izquierdo, asi que con el brazo izquierdo
    estirado taparia al derecho (que agarra). Mismas formas y rayitas que draw_front.arm"""
    def draw(pen):
        oth = 'L' if side == 'R' else 'R'
        sh, e, w = J[oth + '_arm']; LI = pen.c.LI
        shapes = [('c', sh, 0.145)] + tube(sh, e, 0.125, 0.095, bulge=0.15, peak=0.42) + tube(e, w, 0.095, 0.08, bulge=0.12, peak=0.3)
        shapes.append(('c', w + (w - e) / (np.linalg.norm(w - e) + 1e-9) * 0.05, 0.10))
        pen.paint(shapes)
        nn1 = rot((e - sh) / (np.linalg.norm(e - sh) + 1e-9), 90)
        pen.line(smooth_curve([sh + (e - sh) * 0.25 + nn1 * 0.03, sh + (e - sh) * 0.5 + nn1 * 0.05, sh + (e - sh) * 0.8 + nn1 * 0.02]), w=LI * 0.9)
        nn2 = rot((w - e) / (np.linalg.norm(w - e) + 1e-9), 90)
        pen.line(smooth_curve([e + (w - e) * 0.15 - nn2 * 0.03, e + (w - e) * 0.45 - nn2 * 0.04, e + (w - e) * 0.8 - nn2 * 0.015]), w=LI * 0.9)
    return draw


def dedos(J, side):
    """rayitas de los dedos de la mano que agarra, curvados por encima del brazo estirado (hacia el codo)"""
    def draw(pen):
        if not CFG['fingers']:
            return
        oth = 'L' if side == 'R' else 'R'
        w_ = J[oth + '_arm'][2]; ext = J[side + '_arm']
        a = ext[1] - ext[0]; a = a / (np.linalg.norm(a) + 1e-9)             # hombro -> codo del brazo estirado
        for k in (0.13, 0.20, 0.27):
            q = w_ + a * k
            pen.line([q + np.array([0, 0.07]), q + np.array([0, 0.145])], w=pen.c.LI * 0.9)
    return draw


def reloj(J, side, hand_deg):
    def draw(pen):
        if not CFG['clock']:
            return
        sgn = 1 if side == 'R' else -1           # el reloj queda del lado contrario al brazo que cruza
        c = np.array([sgn * CFG['clock_dx'], J['S'][1] + CFG['clock_dy']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


extras = []
hold_n = {'R': 0, 'L': 0}
for i, (s, k) in enumerate(SEQ):
    if k == 'standby':
        extras.append(None)
    elif k == 'swing':
        extras.append([flecha(JF[i], s)])
    else:
        extras.append([brazo_encima(JF[i], s), reloj(JF[i], s, 90 if hold_n[s] == 0 else -10), dedos(JF[i], s)]); hold_n[s] += 1

allp = np.vstack([pts_front(J) for J in JF])
ytop = max(J['S'][1] for J in JF) + CFG['clock_dy'] + CFG['clock_r'] + 0.1
xm = CFG['clock_dx'] + CFG['clock_r'] + 0.1
durs = [{'standby': CFG['durS'], 'swing': CFG['durX'], 'hold': CFG['durH']}[k] for s, k in SEQ]
imgs = render_scene(FRAMES, OUT + 'arm-cross-stretch', durations=[int(x) for x in durs], margin=CFG['margin'],
                    bbox_extra=(-xm, 0.0, xm, max(ytop, allp[:, 1].max())), extras=extras)


# ---------------------------------------------------------------- comprobacion contra workout.js (checkStandbyPosture / checkArmCrossStretch)
def ang3(a, b, c):
    v1 = a - b; v2 = c - b
    return float(np.rad2deg(np.arccos(np.clip(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9), -1, 1))))


def to_img(p, aspect):
    """coordenadas matematicas -> imagen normalizada (0..1) de un encuadre de ancho/alto = aspect; el muñeco ocupa ~80 % del alto"""
    s = 0.8 / (allp[:, 1].max() - allp[:, 1].min())
    return np.array([0.5 + p[0] * s / aspect, 0.9 - (p[1] - allp[:, 1].min()) * s])


def landmarks(J, aspect):
    g = lambda sd: dict(S=to_img(J[sd + '_arm'][0], aspect), E=to_img(J[sd + '_arm'][1], aspect), W=to_img(J[sd + '_arm'][2], aspect))
    return g('L'), g('R')


def standby(J, aspect):
    L, R = landmarks(J, aspect)
    sw = np.hypot(*(L['S'] - R['S'])); mid = (L['S'][1] + R['S'][1]) / 2
    straight = ang3(L['S'], L['E'], L['W']) >= STANDBY_ELBOW_MIN_DEG and ang3(R['S'], R['E'], R['W']) >= STANDBY_ELBOW_MIN_DEG
    down = all(p['W'][1] > mid + STANDBY_WRIST_BELOW_SHOULDER_FACTOR * sw for p in (L, R))    # y de imagen: abajo = mayor
    return bool(straight and down)


def side_ok(ext, oth, shoulder_mid_y, sw):
    elbow = ang3(ext['S'], ext['E'], ext['W'])
    acr = oth['S'][0] - ext['S'][0]
    cross = (ext['W'][0] - ext['S'][0]) / acr if acr else 0
    height = abs(ext['W'][1] - shoulder_mid_y) / sw
    grab = np.hypot(*(oth['W'] - ext['E'])) / sw
    return dict(ok=elbow >= ARM_CROSS_MIN_ELBOW_DEG and cross >= CROSS_MIN_FRACTION and height <= WRIST_HEIGHT_MAX_FACTOR and grab <= GRAB_MAX_FACTOR,
                elbow=elbow, cross=cross, height=height, grab=grab)


def stretch(J, aspect):
    L, R = landmarks(J, aspect)
    sw = np.hypot(*(L['S'] - R['S'])); mid = (L['S'][1] + R['S'][1]) / 2
    return side_ok(L, R, mid, sw), side_ok(R, L, mid, sw)       # (izquierdo estirado, derecho estirado) en coordenadas de imagen


names = ['standby' if k == 'standby' else 'aguante ' + ('D' if s_ == 'R' else 'I') for s_, k in SEQ]
for asp in (16 / 9, 4 / 3, 9 / 16):                              # camara horizontal, 4:3 y vertical (movil)
    for i, (s, k) in enumerate(SEQ):
        sb = standby(JF[i], asp); le, ri = stretch(JF[i], asp)
        if k == 'standby':
            assert sb and not le['ok'] and not ri['ok'], f'{names[i]} (aspecto {asp:.2f}): standby valido y sin estiramiento'
        elif k == 'hold':
            e = ri if s == 'R' else le                            # el brazo estirado
            o = le if s == 'R' else ri                            # el otro lado no debe valer
            assert e['ok'] and not sb, f'{names[i]} (aspecto {asp:.2f}): estiramiento valido {e}'
            if asp == 16 / 9:
                print(f"{names[i]:11s}| codo {e['elbow']:.0f}° (>= {ARM_CROSS_MIN_ELBOW_DEG}) | cruce {e['cross']:.2f} (>= {CROSS_MIN_FRACTION}) | "
                      f"altura muneca {e['height']:.2f} (<= {WRIST_HEIGHT_MAX_FACTOR}) | agarre {e['grab']:.2f} (<= {GRAB_MAX_FACTOR})")
        # cruzando (a medio camino): sin comprobacion, el brazo aun cuelga casi recto y la app es permisiva con ese fotograma
# pies apoyados y brazo estirado recto en el aguante; entre aguantes de un mismo lado nada se mueve salvo el reloj
HOLDS = [i for i, (s_, k) in enumerate(SEQ) if k == 'hold']
for i in HOLDS:
    for sd in 'RL':
        assert abs(JF[i][sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, 'los pies tocan el suelo'
for a, b in [(i, i + 1) for i in HOLDS if i + 1 < len(SEQ) and SEQ[i + 1] == SEQ[i]]:
    assert all(np.allclose(JF[a][sd + '_arm'][j], JF[b][sd + '_arm'][j]) for sd in 'RL' for j in range(3)), 'el muñeco no se mueve entre aguantes'
print('OK: el estiramiento cruzado coincide con los umbrales del contador (armcrossstretch: checkStandbyPosture + checkArmCrossStretch)')
