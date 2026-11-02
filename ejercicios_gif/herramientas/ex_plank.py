"""Plancha (aguante, sobre los ANTEBRAZOS), vista de PERFIL, tumbado boca abajo con la cabeza a la DERECHA (antebrazos y manos al frente, pies atras a la izquierda),
igual que flexiones.gif / superman-hold.gif (mismo muñeco, estilo, suelo y flechas / reloj grises: figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side
no dibuja cara, y aqui NO se usa la funcion cara() de ex_flexiones.py / ex_lsit.py).
Genera UN GIF: plank.gif (slug plank, mode=timed, counter_key=plank): AGUANTE cronometrado.
  tumbado, apoyado en los antebrazos con la cadera y las piernas en el suelo (flechas grises arriba) -> plancha aguantando (reloj gris) -> plancha (reloj con la manecilla avanzada; `clock=0` quita el reloj).
Como lo mira la app (workout.js: checkPlankPosture, constantes PLANK_*), de PERFIL con hombro, codo, muñeca, cadera, rodilla y tobillo del lado mejor visto:
  - cuerpo en LINEA RECTA: hombro-cadera-tobillo >= PLANK_LINE_MIN_DEG (115; ya aguantando 100), rodilla >= PLANK_KNEE_MIN_DEG (125) -> piernas estiradas,
  - tumbado boca abajo, no de pie: inclinacion hombro-tobillo entre PLANK_MIN_TILT_DEG (0) y PLANK_MAX_TILT_DEG (45) (plancha real ~2-25, de pie ~90),
  - apoyado en los ANTEBRAZOS: el codo por debajo del hombro (justo debajo: codos doblados a 90°) y la muñeca por debajo del hombro, con el hombro claramente por encima del codo,
  - la CADERA y las RODILLAS en el aire (solo antebrazos y puntas de los pies apoyados): hipLift = media(altura cadera, altura rodilla sobre el codo) / largo del cuerpo >= PLANK_MIN_HIP_LIFT (0.22),
    es lo que distingue la plancha de la "esfinge" (cadera y piernas en el suelo, que la app rechaza: es el primer fotograma, con las flechas hacia arriba).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), con las medidas en coordenadas de imagen normalizadas (la app no corrige el aspecto en checkPlankPosture).
Uso: python ex_plank.py [carpeta_salida] [clave=valor ...]   (genera plank.gif + PNG de cada fotograma: usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(ey=0.095, hy=0.30, hs=-4, headd=4, foot=292, footF=296, far_t=1.5, far_dx=-0.06, fth=190, fsh=183, ffoot=186, ffar=5.5,
           margin=0.26, arrows=1, clock=1, clock_x=0.0, clock_y=1.28, clock_r=0.27, arr_len=0.42, arr_gap=0.12, aspect=16 / 9,
           dur0=1300, dur1=1400)
# ey: altura del centro del codo (apoyado: el codo toca el suelo); hy: altura de la cadera en la esfinge (cadera y piernas en el suelo)
# hs: grados que la cabeza mira por debajo de la linea del torso en la esfinge (la plancha usa headd por encima: cuello neutro, mirada al suelo un poco por delante)
# foot / footF: angulo del pie cercano / lejano en la plancha (apoyo en las puntas: ~290 = punta hacia abajo); far_t: grados que la pierna lejana se separa de la cercana
# far_dx: cuanto queda el codo / antebrazo LEJANO por detras del cercano (para que se vean los dos); fth/fsh/ffoot/ffar: muslo / espinilla / pie / separacion de la pierna en la esfinge (como superman.gif)
# aspect: ancho/alto del encuadre de la camara con el que se comprueba la plancha (solo afecta al assert de hipLift)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (checkPlankPosture)
PLANK_LINE_MIN_DEG = 115
PLANK_KNEE_MIN_DEG = 125
PLANK_MAX_TILT_DEG = 45
PLANK_MIN_TILT_DEG = 0
PLANK_MIN_SHOULDER_CLEAR = 0.02
PLANK_MIN_HIP_LIFT = 0.22
PLANK_LOOSE_MIN_HIP_LIFT = 0.18


# ---- pie tumbado boca abajo (esfinge): la puntera apunta hacia atras (izquierda) y la masa del pie queda POR DEBAJO de la linea talon-puntera (igual que ex_superman.py);
#      en la plancha (puntera hacia abajo y hacia delante) se usa el pie normal de figura.py
_foot_poly0 = figura.foot_poly


def foot_poly_prone(an, he, to):
    d_ = to - he; L_ = np.linalg.norm(d_) + 1e-9; dr = d_ / L_; up = np.array([-dr[1], dr[0]])
    if up[1] > 0:
        up = -up
    t_ = 1.0
    P_ = [he - dr * 0.035 * t_, to + dr * 0.04 * t_, to + dr * 0.03 * t_ + up * 0.045 * t_,
          he + dr * 0.80 * L_ + up * 0.072 * t_, he + dr * 0.50 * L_ + up * 0.105 * t_,
          an + dr * 0.05 * t_, an - dr * 0.075 * t_ + up * 0.02 * t_,
          he - dr * 0.035 * t_ + up * 0.075 * t_]
    return np.array(P_)


def foot_poly_auto(an, he, to):
    return foot_poly_prone(an, he, to) if (to - he)[0] < 0 else _foot_poly0(an, he, to)


figura.foot_poly = foot_poly_auto

EY = CFG['ey']
SY = EY + L_UA                        # hombro justo ENCIMA del codo (brazo vertical, codos a 90° bajo los hombros)
HY = CFG['hy']
t_s = float(np.rad2deg(np.arcsin((SY - HY) / 1.0)))     # esfinge: inclinacion del tronco para que el hombro quede sobre el codo con la cadera a HY
SX = float(np.cos(np.deg2rad(t_s)))                     # x del hombro (= de los codos y manos, que NO se mueven entre fotogramas)
dF = np.rad2deg(np.arcsin(CFG['far_dx'] / L_UA))        # brazo lejano: el codo queda far_dx por detras del cercano
ARMS = dict(near_arm=('fk', 270, 0), far_arm=('fk', 270 + dF, 0), near_hand=0, far_hand=0)


def feet_low(J):
    lows = []
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        lows += [k[1] - 0.13, he[1] - 0.04, to[1] - 0.04, a[1] - 0.07]
    return min(lows)


def pose_plank(t, sy):
    f = dict(f=1, ground=False, sh=(SX, sy), torso=t, head=t + CFG['headd'])
    return dict(f, near_leg=('fk', 180 + t, 180 + t, CFG['foot']), far_leg=('fk', 180 + t + CFG['far_t'], 180 + t + CFG['far_t'], CFG['footF']), **ARMS)


# PLANCHA: el cuerpo recto gira alrededor de las puntas de los pies; se busca la inclinacion t con la que, con el hombro sobre el codo (altura SY), las puntas tocan el suelo
_T = np.linspace(0.5, 40, 3951)
_dy = np.array([-feet_low(build_side(pose_plank(t, 0.0))) for t in _T])      # altura a la que queda el hombro con los pies apoyados
i_ = int(np.argmin(np.abs(_dy - SY)))
assert abs(_dy[i_] - SY) < 2e-3, 'no hay solucion de postura para la plancha'
t_p = float(_T[i_])
P = pose_plank(t_p, SY)

# ESFINGE (todo apoyado: antebrazos, pecho algo levantado, cadera y piernas en el suelo)
S0 = dict(f=1, ground=False, hip=(0.0, HY), torso=t_s, head=t_s + CFG['hs'],
          near_leg=('fk', CFG['fth'], CFG['fsh'], CFG['ffoot']), far_leg=('fk', CFG['fth'] - CFG['ffar'], CFG['fsh'] - CFG['ffar'], CFG['ffoot']), **ARMS)

JS, JP = build_side(S0), build_side(P)


# ---------------------------------------------------------------- extras: flechas grises y reloj
def flechas(J):
    """dos flechas verticales grises hacia ARRIBA: una sobre la cadera y otra sobre las rodillas (se levantan a la vez)"""
    def f(pen):
        if not CFG['arrows']:
            return
        L_, g = CFG['arr_len'], CFG['arr_gap']
        for x, ytop in ((J['H'][0] + 0.05, J['H'][1] + 0.27), (J['near_leg'][1][0] - 0.05, J['near_leg'][1][1] + 0.22)):
            draw_line_arrow(pen, (x, ytop + g), (x, ytop + g + L_))
    return f


def dedos(J):
    """rayitas de los dedos sobre la mano apoyada (palma plana en el suelo), como en flexiones.gif"""
    def f(pen):
        w_, tip = J['near_arm'][2], J['near_handtip']
        for k_ in (0.12, 0.20):
            x = tip[0] - k_
            pen.line([(x, w_[1] + 0.045), (x, w_[1] + 0.085)], w=pen.c.LI * 0.8)
    return f


def reloj(hand_deg):
    """reloj gris encima del cuerpo (aguante cronometrado): esfera + manecilla larga + corta fija"""
    def draw(pen):
        if not CFG['clock']:
            return
        c = np.array([CFG['clock_x'], CFG['clock_y']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


allp = np.vstack([all_points(JS), all_points(JP)])
bb = (allp[:, 0].min() - 0.1, 0.0, allp[:, 0].max() + 0.1, CFG['clock_y'] + CFG['clock_r'] + 0.1)
render_scene([S0, P, P], OUT + 'plank', durations=[int(CFG['dur0']), int(CFG['dur1']), int(CFG['dur1'])], margin=CFG['margin'], bbox_extra=bb,
             extras=[[flechas(JS), dedos(JS)], [reloj(90), dedos(JP)], [reloj(-10), dedos(JP)]])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (checkPlankPosture)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


xc = (allp[:, 0].min() + allp[:, 0].max()) / 2
Wf = (allp[:, 0].max() - allp[:, 0].min()) / 0.85          # el cuerpo ocupa ~85% del ancho del encuadre
Hf = Wf / CFG['aspect']


def img(p):
    """coordenadas del muñeco (y arriba) -> coordenadas de imagen normalizadas como MediaPipe (x a la derecha, y ABAJO, 0..1; suelo al 80% de la altura)"""
    return np.array([(p[0] - xc) / Wf + 0.5, 0.80 - p[1] / Hf])


def medidas(J, sd='near'):
    S, H = img(J['S']), img(J['H'])
    hp, kn, an = (img(p) for p in J[sd + '_leg'][:3])
    sh, e, w_ = (img(p) for p in J[sd + '_arm'])
    body = float(np.hypot(*(S - an)))
    tilt = float(np.degrees(np.arctan2(abs(an[1] - S[1]), abs(an[0] - S[0]))))
    hipLift = (((e[1] - H[1]) + (e[1] - kn[1])) / 2) / body
    return dict(line=ang3(S, H, an), knee=ang3(H, kn, an), tilt=tilt, hipLift=float(hipLift), shoulderClear=float(e[1] - S[1]),
                elbowBelow=float(e[1] - S[1]), wristBelow=float(w_[1] - S[1]), elbow=ang3(sh, e, w_), ankle_x=float(an[0]), ankle_y=float(an[1]))


def lowest(J):
    ys = [J['H'][1] - 0.20, J['S'][1] - 0.15, J['hd'][1] - 0.27]
    for sd in ('near', 'far'):
        hp, k, a, he, to = J[sd + '_leg']; ys += [k[1] - 0.13, a[1] - 0.07, he[1] - 0.04, to[1] - 0.04]
        sh, e, w_ = J[sd + '_arm']; ys += [e[1] - 0.095, w_[1] - 0.09]
    return min(ys)


mS, mP = medidas(JS), medidas(JP)
print(f"esfinge: tronco {t_s:.0f}°, cadera y={JS['H'][1]:.2f} | hipLift {mS['hipLift']:.2f} (< {PLANK_MIN_HIP_LIFT}: la app la rechaza) | linea {mS['line']:.0f}° rodilla {mS['knee']:.0f}°")
print(f"plancha: tronco {t_p:.1f}°, hombro y={JP['S'][1]:.2f}, cadera y={JP['H'][1]:.2f} | linea {mP['line']:.0f}° rodilla {mP['knee']:.0f}° inclinacion {mP['tilt']:.0f}° "
      f"hipLift {mP['hipLift']:.2f} (encuadre {CFG['aspect']:.2f}:1) codo {mP['elbow']:.0f}° | hombro sobre el codo {mP['shoulderClear']:.2f} del alto de imagen")
# plancha: cuerpo recto, tumbado de verdad (no de pie), piernas estiradas
assert mP['line'] >= PLANK_LINE_MIN_DEG + 40, 'plancha: cuerpo en linea recta (hombro-cadera-tobillo)'
assert mP['knee'] >= PLANK_KNEE_MIN_DEG + 40, 'plancha: piernas estiradas'
assert PLANK_MIN_TILT_DEG <= mP['tilt'] <= PLANK_MAX_TILT_DEG * 0.6, 'plancha: tumbado boca abajo, no de pie'
# apoyado en los antebrazos: codo y muñeca por debajo del hombro (y de imagen mayor), hombro claramente sobre el codo, codo a 90°
assert mP['shoulderClear'] > PLANK_MIN_SHOULDER_CLEAR * 3 and mP['elbowBelow'] > 0 and mP['wristBelow'] > 0, 'plancha: apoyado en los antebrazos'
assert abs(JP['near_arm'][1][0] - JP['S'][0]) < 0.03, 'los codos quedan justo debajo de los hombros'
assert 80 <= mP['elbow'] <= 100, 'codo a ~90°'
# cadera y rodillas en el aire (no tumbado / esfinge)
assert mP['hipLift'] >= PLANK_MIN_HIP_LIFT, 'plancha: cadera y rodillas levantadas (hipLift)'
assert mS['hipLift'] < PLANK_MIN_HIP_LIFT, 'esfinge: la app la rechaza (cadera y piernas en el suelo)'
# los antebrazos y las manos NO se mmueven entre fotogramas; pies y antebrazos tocan el suelo
for k_ in ('near_arm', 'far_arm'):
    assert all(np.allclose(JS[k_][i], JP[k_][i], atol=1e-6) for i in (1, 2)), 'codos y muñecas fijos entre fotogramas'
assert abs(lowest(JP)) < 4e-3, 'plancha: pies y antebrazos tocan el suelo (y=0)'
assert lowest(JS) >= -0.07, 'esfinge: el muñeco no se hunde en el suelo'
assert 0 < mP['ankle_x'] < 1 and 0 < mP['ankle_y'] < 1, 'los pies dentro del encuadre'
print(f"punto mas bajo del muñeco: esfinge y={lowest(JS):+.2f}, plancha y={lowest(JP):+.3f} (el suelo esta en y=0)")
print('OK: la plancha coincide con los umbrales del contador (plank, checkPlankPosture)')
