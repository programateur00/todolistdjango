"""Estiramiento de triceps por encima de la cabeza (overhead triceps stretch), DE ESPALDAS. Mismo muñeco, suelo, flecha y reloj grises que el resto de
GIFs de ejercicios_gif (figura.py, draw_front con back=True). SIN cara (cabeza ovalada lisa: de espaldas no hay nariz, ojos ni oreja).

v3b: el antebrazo del brazo que agarra se dibuja entero (cruza por encima de la parte alta de la cabeza), mismo movimiento que la v3.

Por que de espaldas: de frente (como lo mira la camara) la cabeza TAPA el antebrazo y la mano y no se entiende (v1, descartada); de perfil quedaba enredado
(v2, descartada). De espaldas se ve el brazo subiendo, el codo apuntando al techo, el antebrazo cayendo por detras de la cabeza y la MANO apoyada en la parte
alta de la espalda; el otro brazo pasa por detras de la cabeza (la cabeza lo tapa) y su mano agarra el codo.

Tecnica (Nielasher, Fitbod, Planfit): de pie, un brazo SUBE por encima de la cabeza y se DOBLA por el codo: el codo apunta al techo, junto a la oreja, y la mano
cae por detras de la cabeza hacia la parte alta de la espalda. La otra mano agarra ese codo y tira suave de el hacia la cabeza. Espalda recta, cabeza neutra.
Se aguanta 20-30 s y se cambia de brazo.

Secuencia (6 fotogramas, aguante como plank.gif): 1 de pie, 2 el brazo sube, 3 se dobla el codo y la mano cae a la espalda alta, 4 la otra mano sube,
5 la otra mano agarra el codo y tira (flecha gris + reloj a las 12), 6 igual con la manecilla avanzada.
La camara de la app (counter_key="tricepsoverheadstretch", checkStandbyPosture + checkTricepsOverheadStretch en workout.js, migracion 0032, modo timed)
sigue pidiendo ponerse DE FRENTE; este GIF solo ensena la postura (al final se comprueba tambien contra esos umbrales, mirando el muñeco de frente).
Uso: python ex_triceps_overhead.py [carpeta_salida] [clave=valor ...]   (genera triceps-overhead-stretch.gif + PNG de cada fotograma;
usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(up_ang=84.0, fore_ang=236.0, pull=5.0, grab_dx=-0.04, grab_dy=-0.02, arrows=1, clock=1, fingers=1, clock_dx=1.45, clock_dy=0.35, clock_r=0.27,
           margin=0.30, durS=900, durR=800, durB=900, durH=1500, hip_y=2.0)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

STAND = dict(view='front', back=True, hip=(0, CFG['hip_y']), torso=90, head=90, R_leg=('fk', 272, 272), L_leg=('fk', 268, 268))
ARMS_DOWN = dict(R_arm=('fk', 281, 272), L_arm=('fk', 259, 268))
SW = 0.34
SHR = np.array([SW, 3.0 + (CFG['hip_y'] - 2.0)]); SHL = SHR * np.array([-1, 1])
ELB_R = lambda up: SHR + dv(up) * L_UA


def pose(kind):
    d = dict(STAND)
    if kind == 'stand':
        return dict(d, **ARMS_DOWN)
    if kind == 'raise':                                      # el brazo derecho (de la imagen) sube recto
        return dict(d, R_arm=('fk', 88, 88), L_arm=ARMS_DOWN['L_arm'])
    if kind == 'bend':                                       # codo doblado: la mano cae por detras de la cabeza hasta la espalda alta
        return dict(d, R_arm=('fk', CFG['up_ang'], CFG['fore_ang']), L_arm=ARMS_DOWN['L_arm'])
    if kind == 'approach':                                   # el otro brazo sube
        return dict(d, R_arm=('fk', CFG['up_ang'], CFG['fore_ang']), L_arm=('fk', 132, 28))
    up = CFG['up_ang'] - (CFG['pull'] if kind == 'pull' else 0.0)      # tirando, el codo baja un poco hacia la cabeza
    fore = CFG['fore_ang'] + (CFG['pull'] * 0.5 if kind == 'pull' else 0.0)
    g = ELB_R(up) + np.array([CFG['grab_dx'], CFG['grab_dy']])
    return dict(d, R_arm=('fk', up, fore), L_arm=('ik', tuple(g), 'ccw'))


KINDS = ['stand', 'raise', 'bend', 'approach', 'hold', 'pull']
FRAMES = [pose(k) for k in KINDS]
DURS = [int(CFG[k]) for k in ('durS', 'durR', 'durB', 'durB', 'durH', 'durH')]


def final_J(fr):
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


# ---------------------------------------------------------------- extras
def ua_shapes(sh, e):
    return [('c', sh, 0.145)] + tube(sh, e, 0.125, 0.095, bulge=0.15, peak=0.42) + [('c', e, 0.095)]


def ua_lines(pen, sh, e):
    nn1 = rot((e - sh) / (np.linalg.norm(e - sh) + 1e-9), 90)
    pen.line(smooth_curve([sh + (e - sh) * 0.25 + nn1 * 0.03, sh + (e - sh) * 0.5 + nn1 * 0.05, sh + (e - sh) * 0.8 + nn1 * 0.02]), w=pen.c.LI * 0.9)


def fa_shapes(e, w):
    return tube(e, w, 0.095, 0.08, bulge=0.12, peak=0.3) + [('c', w + (w - e) / (np.linalg.norm(w - e) + 1e-9) * 0.05, 0.10)]


def fa_lines(pen, e, w):
    nn2 = rot((w - e) / (np.linalg.norm(w - e) + 1e-9), 90)
    pen.line(smooth_curve([e + (w - e) * 0.15 - nn2 * 0.03, e + (w - e) * 0.45 - nn2 * 0.04, e + (w - e) * 0.8 - nn2 * 0.015]), w=pen.c.LI * 0.9)


def capas(J, doblado):
    """de espaldas: el antebrazo del brazo que agarra pasa por DELANTE de la cara, asi que la cabeza lo tapa. Se repinta: cabeza y cuello encima de todo, luego
    los dos brazos hasta el codo, el antebrazo del brazo doblado (cae por detras de la cabeza hasta la espalda: se ve entero) y la mano que agarra."""
    def draw(pen):
        S, hd = J['S'], J['hd']
        pen.paint(tube(S + J['ud'] * (-0.02), S + (hd - S) * 0.78, 0.115, 0.10, caps=False))
        v = (hd - S) / (np.linalg.norm(hd - S) + 1e-9)
        th_ = np.linspace(0, 2 * np.pi, 80, endpoint=False); pv = np.array([-v[1], v[0]]); hc = hd + v * 0.035
        pen.paint([('p', hc + np.outer(0.30 * np.sin(th_), v) + np.outer(0.255 * np.cos(th_), pv))])
        for sd in 'RL':
            sh, e, w = J[sd + '_arm']
            pen.paint(ua_shapes(sh, e)); ua_lines(pen, sh, e)
        sh, e, w = J['R_arm']
        pen.paint(fa_shapes(e, w)); fa_lines(pen, e, w)
    return draw


def mano_agarra(J):
    """la mano izquierda (de la imagen) sobre el codo derecho: antebrazo que asoma por el lado de la cabeza, mano y dedos"""
    def draw(pen):
        sh, e, w = J['L_arm']
        eR = J['R_arm'][1]
        u = (w - e) / (np.linalg.norm(w - e) + 1e-9)
        pen.paint(fa_shapes(e, w)); fa_lines(pen, e, w)         # antebrazo ENTERO, por encima de la cabeza (v3b: antes lo tapaba la cabeza y no se veia)
        if CFG['fingers']:
            nn = np.array([-u[1], u[0]])
            for k in (-0.06, 0.0, 0.06):
                q = w + u * 0.03 + nn * k
                pen.line([q, q + u * 0.09], w=pen.c.LI * 0.9)
    return draw


def flecha_tiron(J):
    def draw(pen):
        if not CFG['arrows']:
            return
        e = J['R_arm'][1]
        draw_line_arrow(pen, e + np.array([0.52, 0.18]), e + np.array([0.20, 0.18]))
    return draw


def reloj(J, hand_deg):
    def draw(pen):
        if not CFG['clock']:
            return
        c = np.array([CFG['clock_dx'], J['S'][1] + CFG['clock_dy']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


extras = [None, None, [capas(JF[2], 'R')], [capas(JF[3], 'R')],
          [capas(JF[4], 'R'), mano_agarra(JF[4]), flecha_tiron(JF[4]), reloj(JF[4], 90)],
          [capas(JF[5], 'R'), mano_agarra(JF[5]), flecha_tiron(JF[5]), reloj(JF[5], -10)]]

allp = np.vstack([pts_front(J) for J in JF])
ytop = max(J['S'][1] for J in JF) + CFG['clock_dy'] + CFG['clock_r'] + 0.1
xm = CFG['clock_dx'] + CFG['clock_r'] + 0.1
imgs = render_scene(FRAMES, OUT + 'triceps-overhead-stretch', durations=DURS, margin=CFG['margin'],
                    bbox_extra=(-xm, 0.0, xm, max(ytop, allp[:, 1].max())), extras=extras)


# ---------------------------------------------------------------- comprobaciones
# 1) geometria dibujada: cabeza lisa; en el aguante la mano cae DETRAS de la cabeza (por debajo del cuello de la cabeza, cerca de la columna) y la otra mano
#    queda sobre el codo
for i in (2, 4, 5):
    J = JF[i]; sh, e, w = J['R_arm']
    assert e[1] > J['S'][1] + 0.4, f'fotograma {i + 1}: el codo queda por encima del hombro'
    assert abs(w[0]) < 0.2 and J['S'][1] < w[1] < J['hd'][1], f'fotograma {i + 1}: la mano queda en la espalda alta, bajo la cabeza, cerca de la columna'
for i in (4, 5):
    J = JF[i]
    assert np.linalg.norm(J['L_arm'][2] - J['R_arm'][1]) < 0.12, f'fotograma {i + 1}: la mano que agarra esta sobre el codo'
for J in JF:
    assert J['back'], 'de espaldas'
    for sd in 'RL':
        assert abs(J[sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, 'los pies tocan el suelo'

# 2) mismos umbrales que workout.js (STRETCH_*): la postura, vista de frente, la daria por buena checkTricepsOverheadStretch (el contador sigue pidiendo frente)
STANDBY_ELBOW_MIN_DEG, STANDBY_WRIST_BELOW_SHOULDER_FACTOR = 150, 0.15
TRICEPS_ELBOW_MAX_DEG, TRICEPS_ELBOW_HIGH_FACTOR, TRICEPS_WRIST_NEAR_HEAD_MAX_FACTOR, TRICEPS_GRAB_MAX_FACTOR = 130, 0.25, 2.2, 2.4


def ang3(a, b, c):
    v1 = a - b; v2 = c - b
    return float(np.rad2deg(np.arccos(np.clip(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9), -1, 1))))


def to_img(p, aspect):
    s_ = 0.8 / (allp[:, 1].max() - allp[:, 1].min())
    return np.array([0.5 + p[0] * s_ / aspect, 0.9 - (p[1] - allp[:, 1].min()) * s_])


def lms(J, aspect):
    g = lambda sd: dict(S=to_img(J[sd + '_arm'][0], aspect), E=to_img(J[sd + '_arm'][1], aspect), W=to_img(J[sd + '_arm'][2], aspect))
    return g('L'), g('R'), to_img(J['hd'], aspect)


def standby(J, aspect):
    L, R, _ = lms(J, aspect); sw = np.hypot(*(L['S'] - R['S'])); mid = (L['S'][1] + R['S'][1]) / 2
    return bool(ang3(L['S'], L['E'], L['W']) >= STANDBY_ELBOW_MIN_DEG and ang3(R['S'], R['E'], R['W']) >= STANDBY_ELBOW_MIN_DEG
                and all(p['W'][1] > mid + STANDBY_WRIST_BELOW_SHOULDER_FACTOR * sw for p in (L, R)))


def side_ok(bent, grab, nose, mid, sw):
    el = ang3(bent['S'], bent['E'], bent['W']); hi = (mid - bent['E'][1]) / sw
    ne = np.hypot(*(bent['W'] - nose)) / sw; gd = np.hypot(*(grab['W'] - bent['E'])) / sw
    return dict(ok=el <= TRICEPS_ELBOW_MAX_DEG and hi >= TRICEPS_ELBOW_HIGH_FACTOR and ne <= TRICEPS_WRIST_NEAR_HEAD_MAX_FACTOR and gd <= TRICEPS_GRAB_MAX_FACTOR,
                elbow=el, high=hi, near=ne, grab=gd)


for asp in (16 / 9, 4 / 3, 9 / 16):
    for i in (4, 5):
        L, R, nose = lms(JF[i], asp); sw = np.hypot(*(L['S'] - R['S'])); mid = (L['S'][1] + R['S'][1]) / 2
        r = side_ok(R, L, nose, mid, sw)
        assert r['ok'] and not standby(JF[i], asp), f'fotograma {i + 1} (aspecto {asp:.2f}): estiramiento valido {r}'
        if asp == 16 / 9 and i == 4:
            print(f"aguante | codo {r['elbow']:.0f}° (<= {TRICEPS_ELBOW_MAX_DEG}) | altura codo {r['high']:.2f} (>= {TRICEPS_ELBOW_HIGH_FACTOR}) | "
                  f"muneca-cabeza {r['near']:.2f} (<= {TRICEPS_WRIST_NEAR_HEAD_MAX_FACTOR}) | agarre {r['grab']:.2f} (<= {TRICEPS_GRAB_MAX_FACTOR})")
    assert standby(JF[0], asp), 'standby valido'
print('OK: de espaldas, mano detras de la cabeza, la otra mano sobre el codo; coincide con los umbrales de tricepsoverheadstretch')
