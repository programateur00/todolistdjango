"""Superman, vista de PERFIL, tumbado BOCA ABAJO con la cabeza a la DERECHA (brazos al frente a la derecha, piernas atras a la izquierda), igual que
flexiones.gif (mismo muñeco, estilo, suelo y flechas grises: figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara,
y aqui NO se usa la funcion cara() de ex_lsit.py / ex_flexiones.py).
Genera DOS GIFs con el mismo muñeco:
  - superman.gif       (slug superman, mode=pose, counter_key=superman): REPETICIONES. Todo en el suelo -> subiendo (flechas arriba) -> brazos Y piernas arriba -> bajando (flechas abajo).
  - superman-hold.gif  (slug superman-hold, mode=timed, counter_key=supermanhold): AGUANTE cronometrado. Todo en el suelo (flechas arriba) -> arriba aguantando (reloj gris) -> arriba (reloj avanzado).
Como lo mira la app (workout.js: SupermanTracker / processSuperman / processSupermanHold / createSupermanHoldChecker), de PERFIL con hombro, cadera, rodilla,
tobillo y muñeca del lado que mira:
  - tumbado boca abajo, estirado: inclinacion hombro-cadera <= SUPERMAN_CALIB_MAX_TILT_DEG (20), rodillas estiradas (>= SUPERMAN_CALIB_KNEE_MIN_DEG 140),
  - armRel = (muñeca.y - cadera.y) / largo_tronco ; legRel = (tobillo.y - cadera.y) / largo_tronco (y de imagen hacia abajo); el reposo se aprende tumbado y quieto,
  - "arriba" = subir respecto al reposo: brazo >= SUPERMAN_ARM_UP_LIFT (0.18) y pierna >= SUPERMAN_LEG_UP_LIFT (0.15) a la vez, con la rodilla estirada (>= 120);
    "abajo" = brazo <= SUPERMAN_ARM_DOWN_LIFT (0.08) y pierna <= SUPERMAN_LEG_DOWN_LIFT (0.09),
  - al subir el pecho tambien sube un poco (tronco < SUPERMAN_GETUP_TILT_DEG 30: si se pasa, la app cree que te estas levantando),
  - la CADERA se queda en el suelo; brazos y piernas ESTIRADOS (no se doblan las rodillas).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_superman.py [carpeta_salida] [clave=valor ...]   (genera superman.gif, superman-hold.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(hy=0.30, t0=5, tm=9, t1=14, h0=-6, hm=4, h1=16,
           wr0=0.11, armM=0.13, armU=0.50, legM=0.12, legU=0.46, th0=190, sh0=183,
           far_arm=4, far_leg=5.5, far_up=0.85, foot0=186, foot1=177,
           margin=0.30, arrows=1, clock=1, clock_x=0.0, clock_y=1.38, clock_r=0.27,
           arr_len=0.42, arr_gap=0.30, arr_ax=0.55, arr_lx=-1.55,
           dur0=1200, durm=700, dur1=1300)
# hy: altura de la cadera sobre el suelo (todo el cuerpo apoya: pecho y cadera tocan el suelo, el muñeco no se hunde en la linea gris)
# t0/tm/t1: inclinacion del tronco (grados sobre la horizontal) en reposo / a medio camino / arriba (el pecho sube un poco; el app tolera < 30)
# h0/hm/h1: angulo del cuello-cabeza (cabeza mirando al suelo, algo mas levantada arriba pero SIN mirar al frente)
# wr0: altura de la muñeca en reposo (apoyada en el suelo); armM/armU y legM/legU: cuanto SUBE la muñeca / el tobillo sobre el reposo (largos de tronco) a medio camino / arriba
# th0/sh0: angulo del muslo y de la espinilla en reposo (grados matematicos; 180 = hacia la izquierda, <180 sube); foot0/foot1: direccion del pie en reposo / arriba
# far_arm/far_leg: grados que el brazo / la pierna LEJANOS quedan por encima de los cercanos (para que se vean los dos); far_up: fraccion de la subida que hace el lado lejano
# clock_*, arr_*: posicion del reloj gris y de las flechas
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (SupermanTracker)
SUPERMAN_CALIB_MAX_TILT_DEG = 20
SUPERMAN_CALIB_KNEE_MIN_DEG = 140
SUPERMAN_ARM_UP_LIFT = 0.18
SUPERMAN_LEG_UP_LIFT = 0.15
SUPERMAN_LEG_UP_KNEE_MIN_DEG = 120
SUPERMAN_ARM_DOWN_LIFT = 0.08
SUPERMAN_LEG_DOWN_LIFT = 0.09
SUPERMAN_GETUP_TILT_DEG = 30
REACH = L_UA + L_FA


# ---- pie de tumbado boca abajo: la puntera apunta hacia atras (izquierda) y la planta mira ARRIBA, con el empeine hacia el suelo.
# figura.foot_poly dibuja la masa del pie por ENCIMA de la linea talon-puntera (pie apoyado de planta); aqui se vuelca para que quede por DEBAJO.
_foot_poly0 = figura.foot_poly


def foot_poly_prone(an, he, to):
    d_ = to - he; L_ = np.linalg.norm(d_) + 1e-9; dr = d_ / L_; up = np.array([-dr[1], dr[0]])
    if up[1] > 0:                       # aqui "arriba" del pie (donde queda la masa) = y NEGATIVO
        up = -up
    t_ = 1.0
    P_ = [he - dr * 0.035 * t_, to + dr * 0.04 * t_, to + dr * 0.03 * t_ + up * 0.045 * t_,
          he + dr * 0.80 * L_ + up * 0.072 * t_, he + dr * 0.50 * L_ + up * 0.105 * t_,
          an + dr * 0.05 * t_, an - dr * 0.075 * t_ + up * 0.02 * t_,
          he - dr * 0.035 * t_ + up * 0.075 * t_]
    return np.array(P_)


figura.foot_poly = foot_poly_prone
LEG = L_THIGH + L_SHIN
HY = CFG['hy']


def bisect(f, lo, hi, target, n=60):
    """angulo en [lo, hi] con f(angulo) = target (f monotona)"""
    flo = f(lo) - target
    for _ in range(n):
        mid = (lo + hi) / 2
        if (f(mid) - target > 0) == (flo > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def sh_y(t):
    return HY + np.sin(np.deg2rad(t))


def arm_angle(t, wy):
    """angulo (grados, 0 = hacia la derecha) del brazo ESTIRADO que lleva la muñeca a la altura wy, con el hombro de un tronco inclinado t"""
    return float(np.rad2deg(np.arcsin(np.clip((wy - sh_y(t)) / REACH, -1, 1))))


def ankle_y(th, sh):
    return HY + L_THIGH * np.sin(np.deg2rad(th)) + L_SHIN * np.sin(np.deg2rad(sh))


# muñeca / tobillo en reposo (apoyados en el suelo) -> alturas respecto a la cadera
WR0 = CFG['wr0']
AN0 = ankle_y(CFG['th0'], CFG['sh0'])
armRel0 = WR0 - HY                       # (muñeca - cadera) en reposo, largos de tronco (+ = por encima)
legRel0 = AN0 - HY


def leg_angle_for(lift):
    """pierna ESTIRADA (muslo = espinilla) con el tobillo a 'lift' por encima del reposo (angulo matematico, 180 = hacia la izquierda)"""
    target = AN0 + lift
    return bisect(lambda a: ankle_y(a, a), 150.0, 200.0, target)       # sube al disminuir el angulo


def pose(t, head, arm_lift, leg_lift, foot, rest=False):
    """arm_lift/leg_lift: cuanto suben muñeca/tobillo sobre el reposo (largos de tronco). El lado lejano sube far_up * eso y queda algo por encima."""
    wy = WR0 + arm_lift
    a = arm_angle(t, wy)
    if rest:
        th = CFG['th0']; sh = CFG['sh0']
    else:
        th = sh = leg_angle_for(leg_lift)
    fa = arm_angle(t, WR0 + arm_lift * CFG['far_up']) + CFG['far_arm']
    flg = leg_angle_for(leg_lift * CFG['far_up']) if not rest else None
    if rest:
        fth, fsh = th - CFG['far_leg'], sh - CFG['far_leg']
    else:
        fth = fsh = flg - CFG['far_leg']
    return dict(f=1, ground=False, hip=(0.0, HY), torso=t, head=head,
                near_arm=('fk', a, a), far_arm=('fk', fa, fa),
                near_leg=('fk', th, sh, foot), far_leg=('fk', fth, fsh, foot))


R = pose(CFG['t0'], CFG['h0'], 0.0, 0.0, CFG['foot0'], rest=True)
M = pose(CFG['tm'], CFG['hm'], CFG['armM'], CFG['legM'], (CFG['foot0'] + CFG['foot1']) / 2)
U = pose(CFG['t1'], CFG['h1'], CFG['armU'], CFG['legU'], CFG['foot1'])

JR, JM, JU = (build_side(P) for P in (R, M, U))


# ---------------------------------------------------------------- extras: flechas grises y reloj
def flechas(arriba, J):
    """dos flechas verticales grises: una sobre los brazos y otra sobre las piernas (suben o bajan a la vez)"""
    def f(pen):
        if not CFG['arrows']:
            return
        L_, g = CFG['arr_len'], CFG['arr_gap']
        for x, ytop_src in ((CFG['arr_ax'] + J['near_arm'][2][0] - 0.55 * 0 , J['near_arm'][2][1]), (CFG['arr_lx'], J['near_leg'][2][1])):
            y0 = ytop_src + g + (0 if arriba else L_)
            y1 = ytop_src + g + (L_ if arriba else 0)
            draw_line_arrow(pen, (x, y0), (x, y1))
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


bb = (CFG['arr_lx'] - 0.2, 0.0, CFG['clock_x'] + 3.0, CFG['clock_y'] + CFG['clock_r'] + 0.1)
# ---- repeticiones: en el suelo -> subiendo (flechas arriba) -> arriba -> bajando (flechas abajo)
render_scene([R, M, U, M], OUT + 'superman', durations=[int(CFG['dur0']), int(CFG['durm']), int(CFG['dur1']), int(CFG['durm'])], margin=CFG['margin'],
             bbox_extra=bb, extras=[[], [flechas(True, JM)], [], [flechas(False, JM)]])
# ---- aguante: en el suelo (flechas arriba) -> arriba aguantando (reloj) -> arriba (reloj avanzado)
render_scene([R, U, U], OUT + 'superman-hold', durations=[1300, 1400, 1400], margin=CFG['margin'],
             bbox_extra=bb, extras=[[flechas(True, JU)], [reloj(90)], [reloj(-10)]])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (SupermanTracker)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def medidas(J, sd):
    s, e, w_ = J[sd + '_arm']; hp, k, a = J[sd + '_leg'][:3]
    d = J['S'] - J['H']; T = float(np.linalg.norm(d))
    tilt = float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))
    # en la app la Y de imagen crece hacia ABAJO: aqui y va hacia ARRIBA, asi que (w.y - h.y) de la app = (h.y - w.y) / T aqui
    return dict(tilt=tilt, knee=ang3(hp, k, a), armRel=(hp[1] - w_[1]) / T, legRel=(hp[1] - a[1]) / T, elbow=ang3(s, e, w_), T=T)


def lowest(J):
    ys = [J['H'][1] - 0.20, J['S'][1] - 0.15, J['hd'][1] - 0.27]
    for sd in ('near', 'far'):
        hp, k, a, he, to = J[sd + '_leg']; ys += [k[1] - 0.13, a[1] - 0.07, he[1] - 0.04, to[1] - 0.04]
        sh, e, w_ = J[sd + '_arm']; ys += [e[1] - 0.095, w_[1] - 0.09]
    return min(ys)


names = (('reposo', JR), ('medio', JM), ('arriba', JU))
m0s = {sd: medidas(JR, sd) for sd in ('near', 'far')}     # reposo de cada lado: baseArm / baseLeg de la app (lo que se aprende tumbado)
for nm, J in names:
    for sd in ('near', 'far'):
        m = medidas(J, sd)
        print(f"{nm:7s} {sd:4s}: tronco {m['tilt']:.0f}° | codo {m['elbow']:.0f}° | rodilla {m['knee']:.0f}° | brazo_sube {m0s[sd]['armRel'] - m['armRel']:+.2f} pierna_sube {m0s[sd]['legRel'] - m['legRel']:+.2f}")
    print(f"{'':7s} punto mas bajo del muñeco y={lowest(J):+.2f}")

for sd in ('near', 'far'):
    m0, mM, m1 = (medidas(J, sd) for J in (JR, JM, JU))
    # reposo: tumbado y estirado, para calibrar
    assert m0['tilt'] <= SUPERMAN_CALIB_MAX_TILT_DEG, 'reposo: tronco tumbado (calibracion)'
    assert m0['knee'] >= SUPERMAN_CALIB_KNEE_MIN_DEG, 'reposo: piernas estiradas (calibracion)'
    # el reposo de referencia es el del lado cercano (en la app se aprende por lado); aqui el lado lejano se mide contra su propio reposo
    arm0, leg0 = m0['armRel'], m0['legRel']
    for nm, m in (('medio', mM), ('arriba', m1)):
        assert m['tilt'] < SUPERMAN_GETUP_TILT_DEG, f'{nm}: el pecho sube pero no debe parecer que te levantas (< {SUPERMAN_GETUP_TILT_DEG}°)'
    assert m1['tilt'] <= 20, 'arriba: pecho elevado como mucho 20° (SUPERMAN_CALIB_MAX_TILT_DEG)'
    armL, legL = arm0 - m1['armRel'], leg0 - m1['legRel']       # app: baseArm - armS (y de imagen hacia abajo)
    assert m1['knee'] >= SUPERMAN_LEG_UP_KNEE_MIN_DEG and m1['knee'] >= 165, 'arriba: piernas estiradas'
    assert armL >= SUPERMAN_ARM_UP_LIFT * 1.5 and legL >= SUPERMAN_LEG_UP_LIFT * 1.5, 'arriba: brazos Y piernas suben con margen sobre el umbral'
    # a medio camino: ni "arriba" ni "abajo" (zona de histeresis)
    aM, lM = arm0 - mM['armRel'], leg0 - mM['legRel']
    assert SUPERMAN_ARM_DOWN_LIFT < aM < SUPERMAN_ARM_UP_LIFT and SUPERMAN_LEG_DOWN_LIFT < lM < SUPERMAN_LEG_UP_LIFT, 'medio: ni arriba ni abajo'
    assert m1['elbow'] >= 170 and mM['elbow'] >= 170, 'brazos estirados'
assert lowest(JR) >= -0.07 and lowest(JU) >= -0.07, 'el muñeco no se hunde en el suelo'
print('OK: reposo / medio / arriba coinciden con los umbrales del contador (SupermanTracker)')
