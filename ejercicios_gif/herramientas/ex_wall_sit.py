"""Silla en pared (wall sit), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo, pared y reloj gris que handstand / plank. SIN cara (cabeza lisa: ni nariz, ni ojo, ni oreja, ni barbilla: plain_head).
Como lo mira la app (workout.js: checkWallSitPosture, counter "wallsit", slug wall-sit, mode=timed): AGUANTE cronometrado, de PERFIL,
con hombro-cadera-rodilla-tobillo del lado mejor visto:
  - RODILLA (cadera-rodilla-tobillo) entre WALLSIT_KNEE_MIN_DEG = 65 y WALLSIT_KNEE_MAX_DEG = 115  -> el GIF la pone a 90°,
  - CADERA (hombro-cadera-rodilla) entre WALLSIT_HIP_MIN_DEG = 60 y WALLSIT_HIP_MAX_DEG = 135     -> 90°,
  - TRONCO recto y apoyado: inclinacion sobre la horizontal >= WALLSIT_TORSO_MIN_TILT_DEG = 50     -> 90° (vertical).
Forma correcta (la de las guias de wall sit): espalda ENTERA pegada a la pared (y la cabeza apoyada), muslos paralelos al suelo, espinillas verticales
con las rodillas justo encima de los tobillos, pies planos en el suelo (pies fijos), manos apoyadas en los muslos (no en la pared ni en las rodillas).
GIF de 3 fotogramas (igual que plank): bajando por la pared con flecha gris abajo -> sentada/o con el reloj gris en las 12 -> igual con la manecilla avanzada.
Los pies NO se mueven en ningun fotograma (el 1o es la misma postura a mitad de bajada, con las rodillas a ~130°).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), con las medidas en coordenadas de imagen normalizadas
(la app no corrige el aspecto) y en los aspectos 16:9, 4:3 y 1:1.
Uso: python ex_wall_sit.py [carpeta_salida] [clave=valor ...]   (genera wall-sit.gif + PNG de cada fotograma; usar una carpeta temporal para probar)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(xa=0.95, hM=1.38, head=-1, far_dx=-0.07, hand_f=0.55, hand_off=0.075, far_hand_dx=0.12, wall=1, wall_gap=0.0, margin=0.12,
           clock=1, clock_dx=0.98, clock_dy=0.50, clock_r=0.27, arrows=1, arrow_dx=0.88, arrow_len=0.6, arrow_dy=0.0,
           durA=1100, durB=1400, durC=1400)
# xa: distancia horizontal cadera(pared) -> tobillo en unidades de torso; 0.95 = largo del muslo, o sea la espinilla queda VERTICAL con la rodilla sobre el tobillo
# hM: altura de la cadera sobre el tobillo en el fotograma 1 (bajando); en la silla es la longitud de la espinilla (0.92)
# head: angulo de la cabeza (grados); -1 = automatico (la cabeza apoya justo en la pared, igual que la espalda)
# far_dx: pie lejano algo mas atras para que se vean los dos; hand_f / hand_off: donde apoya la mano en el muslo (fraccion cadera->rodilla / separacion sobre el muslo)
# far_hand_dx: la mano lejana queda algo mas adelante para que se vea; wall=0 quita la pared; wall_gap: separacion espalda-pared
# clock_dx / clock_dy / clock_r: posicion del reloj respecto al tobillo y al hombro; arrow_*: flecha gris del fotograma 1; dur*: ms por fotograma
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
WALLSIT_KNEE_MIN_DEG, WALLSIT_KNEE_MAX_DEG = 65, 115
WALLSIT_HIP_MIN_DEG, WALLSIT_HIP_MAX_DEG = 60, 135
WALLSIT_TORSO_MIN_TILT_DEG = 50
LW_U = 0.052                   # grosor del contorno de tinta en unidades de torso (Canvas.LW / scale)

XA = CFG['xa']


# ---- geometria del torso (copia de figura.draw_side) para apoyar la espalda EXACTAMENTE en la pared
RB0 = [(-0.14, .13), (0.0, .19), (0.12, .26), (0.30, .25), (0.52, .20), (0.76, .18), (1.0, .225), (1.12, .235)]
RB = [(a, b * 1.18) for a, b in RB0]
_S = np.linspace(-0.14, 0.90, 30)
_Rb = np.interp(_S, [p_[0] for p_ in RB], [p_[1] for p_ in RB])
_k = np.hanning(9)[1:-1]; _k /= _k.sum()
BACK = float(np.convolve(np.pad(_Rb, 3, mode='edge'), _k, mode='valid').max())      # lo mas atras que llega la espalda (torso vertical, x = 0 en la cadera)


def head_back_x(head_deg, S=np.array([0.0, 1.0])):
    """x mas a la izquierda de la cabeza (elipse de figura.draw_side con plain_head) para torso vertical con la cadera en x = 0"""
    v = dv(head_deg); hd = S + v * NECK_HEAD; hc = hd + v * 0.035
    th_ = np.linspace(0, 2 * np.pi, 720, endpoint=False); ra, rb_ = 0.30, 0.245
    ax_ = np.arctan2(v[1], v[0])
    return float((hc[0] + ra * np.cos(th_) * np.cos(ax_) - rb_ * np.sin(th_) * np.sin(ax_)).min())


if CFG['head'] < 0:        # cabeza apoyada en la pared (la espalda esta en x = -BACK): se gira hacia atras hasta tocar
    lo, hi = 90.0, 110.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if head_back_x(mid) > -BACK:
            lo = mid
        else:
            hi = mid
    HEAD = lo
else:
    HEAD = CFG['head']
X_WALL = -BACK - LW_U - CFG['wall_gap']        # el contorno de la espalda toca la raya de la pared


def thigh_r(f):
    """radio del muslo (figura.draw_leg: tube 0.20 -> 0.135 con bulge 0.09, peak 0.4)"""
    s_ = f
    return (0.20 + (0.135 - 0.20) * s_) * (1 + 0.09 * np.sin(np.pi * s_ ** (np.log(0.5) / np.log(0.4))))


def pose(h):
    H = np.array([0.0, h]); A = np.array([XA, 0.0]); AF = A + np.array([CFG['far_dx'], 0.0])
    K, _ = ik2(H, A, L_THIGH, L_SHIN, 'ccw')
    t = (K - H) / np.linalg.norm(K - H); n = np.array([-t[1], t[0]])
    f = CFG['hand_f']
    W = H + t * (f * L_THIGH) + n * (thigh_r(f) + CFG['hand_off'])          # muñeca apoyada en el muslo
    WF = W + t * CFG['far_hand_dx']
    return dict(f=1, ground=True, plain_head=True, hip=tuple(H), torso=90, head=HEAD,
                near_leg=('ik', tuple(A), 'ccw', 0), far_leg=('ik', tuple(AF), 'ccw', 0),     # pies planos, puntas hacia delante
                near_arm=('ik', tuple(W), 'cw'), far_arm=('ik', tuple(WF), 'cw'),             # codo hacia atras, antebrazo apoyado
                near_hand=ang(t), far_hand=ang(t))


SIT = pose(L_SHIN)         # rodilla justo encima del tobillo: muslo horizontal, espinilla vertical
MID = pose(CFG['hM'])
frames = [MID, SIT, SIT]
durs = [int(CFG['durA']), int(CFG['durB']), int(CFG['durC'])]
JS = [build_side(p_) for p_ in frames]
JSs = [shift_J(J, ground_shift(J)) for J in JS]      # coordenadas con el suelo en y=0 (las mismas que usa render_scene)
J_MID, J_SIT = JSs[0], JSs[1]


# ---- la pared: raya gris vertical del suelo hasta arriba del todo (mismo gris y grosor que el suelo), DETRAS del muñeco
def pared(pen):
    if not CFG['wall']:
        return
    x = pen.c.C((X_WALL, 0))[0]; fy = pen.c.C((0, -0.055))[1]
    cv2.line(pen.img, (int(round(x)), 0), (int(round(x)), int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)


_draw_side = figura.draw_side


def draw_side_con_pared(pen, J_, props_back=None):
    pared(pen)
    _draw_side(pen, J_, props_back)


figura.draw_side = draw_side_con_pared


def flecha(pen):
    """flecha gris hacia abajo, a la derecha del pecho (la espalda baja deslizandose por la pared)"""
    if not CFG['arrows']:
        return
    x = XA - (XA - CFG['arrow_dx']); ytop = J_MID['S'][1] + CFG['arrow_dy']
    draw_line_arrow(pen, (x, ytop), (x, ytop - CFG['arrow_len']))


def reloj(hand_deg):
    """reloj gris al lado de la cabeza (aguante cronometrado): esfera + manecilla larga + corta fija (igual que handstand / l-sit-hold)"""
    def draw(pen):
        if not CFG['clock']:
            return
        c = np.array([CFG['clock_dx'], J_SIT['S'][1] + CFG['clock_dy']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


allp = np.vstack([all_points(J) for J in JSs])
toe_x = max(J[s_ + '_leg'][4][0] for J in JSs for s_ in ('near', 'far'))
x1 = max(toe_x, CFG['clock_dx'] + CFG['clock_r']) + 0.2
bb = (X_WALL - 0.1, -0.1, x1, max(J['hd'][1] for J in JSs) + 0.40)
imgs = render_scene(frames, OUT + 'wall-sit', durations=durs, margin=CFG['margin'], bbox_extra=bb,
                    extras=[[flecha], [reloj(90)], [reloj(-10)]])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (checkWallSitPosture)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


xc = (allp[:, 0].min() + allp[:, 0].max()) / 2
Wf = (allp[:, 0].max() - allp[:, 0].min()) / 0.85


def make_img(aspect):
    Hf = Wf / aspect

    def img(p):
        return np.array([(p[0] - xc) / Wf + 0.5, 0.95 - p[1] / Hf])      # x a la derecha, y ABAJO (como MediaPipe)
    return img


def tilt(p, q):
    d = q - p
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


def medidas(J, img):
    S, H = img(J['S']), img(J['H'])
    kn, an = img(J['near_leg'][1]), img(J['near_leg'][2])
    return dict(knee=ang3(H, kn, an), hip=ang3(S, H, kn), tilt=tilt(S, H))


def ok_wallsit(m):
    return (m['tilt'] >= WALLSIT_TORSO_MIN_TILT_DEG and WALLSIT_KNEE_MIN_DEG <= m['knee'] <= WALLSIT_KNEE_MAX_DEG
            and WALLSIT_HIP_MIN_DEG <= m['hip'] <= WALLSIT_HIP_MAX_DEG)


for asp in (16 / 9, 4 / 3, 1.0):
    img = make_img(asp)
    mMid, mSit = medidas(J_MID, img), medidas(J_SIT, img)
    if asp == 16 / 9:
        print(f"silla : rodilla {mSit['knee']:5.1f}° (65-115) | cadera {mSit['hip']:5.1f}° (60-135) | tronco {mSit['tilt']:4.1f}° (>= 50) | "
              f"cadera ({J_SIT['H'][0]:+.2f}, {J_SIT['H'][1]:.2f}) rodilla ({J_SIT['near_leg'][1][0]:+.2f}, {J_SIT['near_leg'][1][1]:.2f}) "
              f"tobillo ({J_SIT['near_leg'][2][0]:+.2f}, {J_SIT['near_leg'][2][1]:.2f})")
        print(f"bajando: rodilla {mMid['knee']:5.1f}° | cadera {mMid['hip']:5.1f}° | tronco {mMid['tilt']:4.1f}° -> aun no cuenta (rodilla > {WALLSIT_KNEE_MAX_DEG})")
    assert ok_wallsit(mSit), f'la silla debe pasar checkWallSitPosture (aspecto {asp:.2f}): {mSit}'
    assert abs(mSit['knee'] - 90) < 3 and abs(mSit['hip'] - 90) < 3 and mSit['tilt'] > 88, 'silla a 90°, torso vertical'
    assert not ok_wallsit(mMid) and mMid['knee'] > WALLSIT_KNEE_MAX_DEG, 'el fotograma de bajada aun no es la postura (rodilla > 115)'
    assert mMid['tilt'] > 88, 'bajando, la espalda sigue vertical pegada a la pared'

# --- forma: espalda y cabeza en la pared, muslos paralelos, espinillas verticales, rodillas sobre los tobillos, pies fijos y planos, manos en los muslos
J0 = JSs[0]
for J in JSs:
    for sd in ('near', 'far'):
        hp, kn, an, he, to = J[sd + '_leg']
        assert abs(min(he[1] - 0.04, to[1] - 0.04, an[1] - 0.07)) < 3e-3, 'los pies deben tocar el suelo'
        assert abs(an[0] - J0[sd + '_leg'][2][0]) < 2e-3 and abs(to[0] - J0[sd + '_leg'][4][0]) < 2e-3, 'los pies no se mueven'
        assert abs(an[1] - J0[sd + '_leg'][2][1]) < 2e-3, 'tobillo a la misma altura en todos los fotogramas'
    assert abs(J['S'][0] - J['H'][0]) < 1e-6, 'torso vertical (espalda recta, pegada a la pared)'
    assert J['hd'][0] > X_WALL, 'la cabeza no atraviesa la pared'
S_, H_ = J_SIT['S'], J_SIT['H']
kn, an = J_SIT['near_leg'][1], J_SIT['near_leg'][2]
assert abs(kn[1] - H_[1]) < 1e-3, 'muslo paralelo al suelo (rodilla a la altura de la cadera)'
assert abs(kn[0] - an[0]) < 1e-3, 'rodilla justo encima del tobillo (espinilla vertical)'
assert abs(H_[1] - kn[1]) < 1e-3 and abs(H_[0] - 0.0) < 1e-9, 'cadera pegada a la pared'
for sd in ('near', 'far'):
    sh, e, w = J_SIT[sd + '_arm']
    hp, k_, a_, he_, to_ = J_SIT[sd + '_leg']
    assert H_[0] + 0.3 < w[0] < k_[0] + 0.1 and H_[1] < w[1] < H_[1] + 0.45, 'las manos descansan sobre los muslos'
# espalda: el contorno de tinta de la espalda toca la raya de la pared (ni la atraviesa ni queda separada)
assert abs((-BACK - LW_U) - X_WALL) < 1e-9 or CFG['wall_gap'] != 0 or not CFG['wall']
hb = head_back_x(HEAD)
assert hb >= -BACK - 1e-3, 'la cabeza no sobresale por detras de la espalda'
print(f"OK: silla en pared coincide con los umbrales del contador (wallsit): rodilla 90° (65-115), cadera 90° (60-135), tronco vertical (>= 50); "
      f"espalda en la pared (x={X_WALL:+.3f}), cabeza a {abs(hb + BACK):.3f} de la espalda (angulo {HEAD:.1f}°); aspectos 16:9, 4:3 y 1:1")
