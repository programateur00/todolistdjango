"""Plancha lateral (aguante), vista DE FRENTE (la camara ve la barriga), tumbado de lado con la cabeza a la DERECHA y los pies a la izquierda,
igual que hollow-body-hold.gif / superman-hold.gif (mismo muñeco, estilo y suelo: figura.py) y con las flechas / el reloj grises de
hollow-body-hold.gif / l-sit-hold.gif. SIN cara (ni nariz ni ojo ni oreja: figura.draw_front no dibuja cara y aqui NO se usa ninguna funcion cara()).
Genera UN GIF: side-plank.gif (slug side-plank, mode=timed, counter_key=sideplank): AGUANTE cronometrado.
  apoyado en el antebrazo con la cadera en el suelo (flecha gris hacia arriba) -> plancha lateral aguantando (reloj gris) -> plancha lateral (reloj con la manecilla avanzada; `clock=0` quita el reloj).
Como lo mira la app (workout.js: checkSidePlankPosture, constantes SIDEPLANK_*), con los landmarks de MediaPipe en la imagen (y hacia ABAJO):
  - el lado "de abajo" (el que apoya) es el del hombro MAS BAJO en la imagen: se ven los dos hombros uno encima del otro (por eso la camara ve la barriga, no el perfil),
  - lineAngle = angulo hombro-cadera-tobillo del lado de abajo >= SIDEPLANK_LINE_MIN_DEG (145): cuerpo en linea recta,
  - tilt = inclinacion hombro->cadera sobre la horizontal <= SIDEPLANK_MAX_TILT_DEG (45): tumbado de lado, no de pie,
  - hipLift = (altura media de codo y tobillo de abajo [= suelo] - altura de la cadera) / ancho de hombros, entre SIDEPLANK_MIN_HIP_LIFT (0.22) y SIDEPLANK_MAX_HIP_LIFT (1.2): cadera ALZADA,
  - elbowDrop = (codo - hombro de abajo) / ancho de hombros >= SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN (0.22): codo justo debajo del hombro, apoyado,
  - armDown = (muñeca - hombro de abajo) / ancho de hombros >= PLANK_ARMS_DOWN_MARGIN (0.3): antebrazo de abajo apoyado en el suelo,
  - la mano de arriba puede ir donde sea (aqui estirada al techo, la plancha lateral clasica; `arm_up=0` la pone sobre la cadera, como dice la nota de task_workout.html).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_side_plank.py [carpeta_salida] [clave=valor ...]   (genera side-plank.gif + PNG de cada fotograma: usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(sw=0.34,                               # semi-ancho de hombros (figura.build_front: shoulder_w)
           e_y=0.10,                              # altura del codo / mano de apoyo sobre el suelo (radio del brazo ~0.095)
           uaA=0.86,                              # fraccion del brazo de apoyo que se ve en el fotograma 1 (apoyado en el antebrazo, hombro mas bajo)
           fa=0.42, fa_dir=180,                   # antebrazo de apoyo: fraccion de su largo (esta de frente, en escorzo) y direccion (180 = hacia los pies)
           arm_up=1, up_dx=-0.02, up_dy=0.30,     # mano de arriba: 1 = estirada al techo, 0 = sobre la cadera; up_dx/up_dy: posicion de la mano sobre la cadera
           head_dt=0, margin=0.30, arrows=1, clock=1, clock_r=0.27, clock_dx=0.15, clock_dy=0.25,
           arr_len=0.42, arr_gap=0.24, arr_x=0.0, stack=0.17, dur0=1300, dur1=1400)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (checkSidePlankPosture)
SIDEPLANK_LINE_MIN_DEG = 145
SIDEPLANK_MAX_TILT_DEG = 45
SIDEPLANK_MIN_HIP_LIFT = 0.22
SIDEPLANK_MAX_HIP_LIFT = 1.2
SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN = 0.22
PLANK_ARMS_DOWN_MARGIN = 0.3
LYING_FLAT_MIN_DEG = 135            # paso 1 (tumbarse del todo)
MIN_BODY_LENGTH_FACTOR = 1.8        # largo hombro-tobillo / ancho de hombros

SW = CFG['sw']
HW = 0.15                           # semi-ancho de caderas (figura.build_front)
LEG = L_THIGH + L_SHIN
FOOT_DROP, FOOT_SIDE, FOOT_RY = 0.10, 0.03, 0.08   # zapatilla de figura.draw_front: centro = tobillo - ud*0.10 + n*fd*0.03, semieje vertical 0.08


def nvec(t):                        # figura.build_front: n = dv(t - 90)
    return dv(t - 90)


def foot_bottom(an, t, fd):
    n = nvec(t); ud = dv(t)
    return float((an - ud * FOOT_DROP + n * fd * FOOT_SIDE)[1] - FOOT_RY)


def bisect(f, lo, hi, it=60):
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (flo > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------- fotograma 2/3: plancha lateral (cadera alzada, cuerpo recto)
def solve_plank():
    def feet_gap(t):                 # suelo: codo (e_y) y pie de abajo a la vez
        n = nvec(t)
        Sy = CFG['e_y'] + L_UA + SW * np.cos(np.deg2rad(t))          # hombro de abajo = codo + brazo vertical
        Hy = Sy - np.sin(np.deg2rad(t))
        hp = np.array([0, Hy]) + n * HW
        an = hp + dv(t + 180) * LEG
        return foot_bottom(an, t, +1)
    t = bisect(feet_gap, 4.0, 35.0)
    Sy = CFG['e_y'] + L_UA + SW * np.cos(np.deg2rad(t))
    return t, Sy - np.sin(np.deg2rad(t))


tB, HyB = solve_plank()


def leg_stack(t, Hy):
    """pierna de abajo recta en la linea del cuerpo; pierna de arriba apilada encima (tobillo a CFG['stack'] por encima del otro)"""
    n = nvec(t)
    hp = np.array([0, Hy]) + n * HW
    an = hp + dv(t + 180) * LEG
    tgt = an + np.array([0, CFG['stack']])
    return dict(R_leg=('fk', t + 180, t + 180, +1), L_leg=('ik', tgt, 'cw', +1))


def pose(t, Hy, ua=1.0, up=None):
    up = CFG['arm_up'] if up is None else up
    n = nvec(t)
    H = np.array([0, Hy]); S = H + dv(t)
    p = dict(view='front', ground=False, hip=(0, Hy), torso=t, head=t + CFG['head_dt'], shoulder_w=SW,
             R_arm=('fk', 270, CFG['fa_dir']), fore_R_fa=CFG['fa'], fore_R_ua=ua, **leg_stack(t, Hy))
    if up:
        p['L_arm'] = ('fk', 90, 90)
    else:   # mano de arriba sobre la cadera de arriba (codo hacia arriba)
        shL = S - n * SW
        tgt = H - n * (HW + CFG['up_dy']) + dv(t + 180) * (-CFG['up_dx'])
        p['L_arm'] = ('ik', tgt, 'cw')
    return p


PB = pose(tB, HyB)


# ---------------------------------------------------------------- fotograma 1: cadera en el suelo, apoyado en el antebrazo
def hull_bottom(J):
    """punto mas bajo de la cadera (el pantalon corto de figura.draw_front): 2 puntos del cinturon + redondeo de cada muslo"""
    S, H, n = J['S'], J['H'], J['n']
    ys = [(S + (H - S) * s2 + n * sg * wd)[1] for sg in (1, -1) for s2, wd in ((0.80, 0.27), (1.0, 0.31))]
    for sd in 'RL':
        hp = J[sd + '_leg'][0]; ys.append(hp[1] - 0.21)
    return min(ys)


def build_A(t):
    # el hombro de abajo queda sobre el codo (brazo de apoyo vertical algo mas corto: apoyado en el antebrazo, hombro mas bajo) y la cadera apoya en el suelo
    n = nvec(t)
    Sy = CFG['e_y'] + L_UA * CFG['uaA'] + SW * np.cos(np.deg2rad(t))
    Hy = Sy - np.sin(np.deg2rad(t))
    return Hy


def solve_lying():
    def f(t):
        Hy = build_A(t)
        J = figura.build_front(pose_lying(t, Hy))
        return hull_bottom(J)
    return bisect(f, 20.0, 60.0)


def pose_lying(t, Hy):
    n = nvec(t)
    hp = np.array([0, Hy]) + n * HW
    # piernas casi planas sobre el suelo hacia la izquierda; el angulo se ajusta para que el pie de abajo apoye
    def fg(phi):
        an = hp + dv(phi) * LEG
        return foot_bottom(an, t, +1)
    phi = bisect(fg, 170.0, 200.0)
    an = hp + dv(phi) * LEG
    p = dict(view='front', ground=False, hip=(0, Hy), torso=t, head=t + CFG['head_dt'], shoulder_w=SW,
             R_arm=('fk', 270, CFG['fa_dir']), fore_R_fa=CFG['fa'], fore_R_ua=CFG['uaA'],
             R_leg=('fk', phi, phi, +1), L_leg=('ik', an + np.array([0, CFG['stack']]), 'cw', +1))
    S = np.array([0, Hy]) + dv(t)
    if CFG['arm_up']:
        p['L_arm'] = ('fk', 90, 90)
    else:
        H = np.array([0, Hy])
        tgt = H - n * (HW + CFG['up_dy']) + dv(t + 180) * (-CFG['up_dx'])
        p['L_arm'] = ('ik', tgt, 'cw')
    return p


tA = solve_lying(); HyA = build_A(tA)
PA = pose_lying(tA, HyA)

JA, JB = build_front(PA), build_front(PB)


# ---------------------------------------------------------------- extras: flecha gris y reloj
def flecha(J):
    def f(pen):
        if not CFG['arrows']:
            return
        x = J['H'][0] + CFG['arr_x']
        ytop = J['H'][1] + 0.62
        draw_line_arrow(pen, (x, ytop), (x, ytop + CFG['arr_len']))
    return f


def clock_center():
    return np.array([JB['H'][0] + CFG['clock_dx'], JB['hd'][1] + 0.40 + CFG['clock_dy']])


def reloj(hand_deg):
    def draw(pen):
        if not CFG['clock']:
            return
        c = clock_center(); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


allp = np.vstack([pts_front(JA), pts_front(JB)])
cc = clock_center()
bb = (allp[:, 0].min() - 0.1, 0.0, allp[:, 0].max() + 0.1, max(allp[:, 1].max(), cc[1] + CFG['clock_r']) + 0.1)
render_scene([PA, PB, PB], OUT + 'side-plank', durations=[int(CFG['dur0']), int(CFG['dur1']), int(CFG['dur1'])], margin=CFG['margin'],
             bbox_extra=bb, extras=[[flecha(JA)], [reloj(90)], [reloj(-10)]])


# ---------------------------------------------------------------- comprobacion contra workout.js (checkSidePlankPosture)
def img(p):                          # coordenadas de imagen (y hacia abajo), como MediaPipe
    return np.array([p[0], -p[1]], float)


def app_measures(J):
    sh = {s: img(J[s + '_arm'][0]) for s in 'RL'}
    sw = float(np.linalg.norm(sh['R'] - sh['L']))
    down = 'R' if sh['R'][1] > sh['L'][1] else 'L'
    S_, E_, W_ = (img(x) for x in J[down + '_arm'])
    hp, kn, an = (img(x) for x in J[down + '_leg'][:3])
    ang = lambda a, b, c: float(np.degrees(np.arccos(np.clip(np.dot(a - b, c - b) / (np.linalg.norm(a - b) * np.linalg.norm(c - b)), -1, 1))))
    ground = (E_[1] + an[1]) / 2
    return dict(down=down, line=ang(S_, hp, an), tilt=float(np.degrees(np.arctan2(abs(hp[1] - S_[1]), abs(hp[0] - S_[0])))),
                hipLift=(ground - hp[1]) / sw, elbowDrop=(E_[1] - S_[1]) / sw, armDown=(W_[1] - S_[1]) / sw,
                bodyLen=float(np.linalg.norm(S_ - an)) / sw, elbowX=E_[0] - S_[0], sw=sw)


mA, mB = app_measures(JA), app_measures(JB)
for nm, m in (('fotograma 1 (cadera abajo)', mA), ('plancha lateral', mB)):
    print(f"{nm:27s} lado abajo={m['down']} linea {m['line']:.0f}° tilt {m['tilt']:.0f}° hipLift {m['hipLift']:.2f} elbowDrop {m['elbowDrop']:.2f} armDown {m['armDown']:.2f} largo {m['bodyLen']:.1f} anchos de hombro")
assert mB['down'] == 'R' and mA['down'] == 'R', 'el lado de abajo (hombro mas bajo) es el que apoya'
assert mB['line'] >= SIDEPLANK_LINE_MIN_DEG + 15, 'plancha lateral: cuerpo en linea recta (con margen)'
assert mB['tilt'] <= SIDEPLANK_MAX_TILT_DEG * 0.6, 'tumbado de lado, no de pie'
assert SIDEPLANK_MIN_HIP_LIFT * 1.5 <= mB['hipLift'] <= SIDEPLANK_MAX_HIP_LIFT * 0.8, 'cadera alzada con margen y sin pasarse'
assert mB['elbowDrop'] >= SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN * 2, 'codo bien por debajo del hombro'
assert abs(mB['elbowX']) < 0.1, 'codo justo debajo del hombro'
assert mB['armDown'] >= PLANK_ARMS_DOWN_MARGIN * 2, 'antebrazo de abajo apoyado'
assert mB['bodyLen'] >= MIN_BODY_LENGTH_FACTOR, 'cuerpo entero extendido'
assert mA['hipLift'] < SIDEPLANK_MIN_HIP_LIFT, 'fotograma 1: cadera apoyada (aun no cuenta)'
assert mA['line'] >= LYING_FLAT_MIN_DEG, 'fotograma 1: cuerpo estirado de lado'
print('OK: la plancha lateral coincide con los umbrales del contador (sideplank, checkSidePlankPosture)')
