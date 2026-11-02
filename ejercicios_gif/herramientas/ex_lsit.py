"""L-sit en paralelas, vista de PERFIL (de lado a la camara), mirando a la DERECHA como en fondos / dominadas-commando.
Genera DOS GIFs con el mismo muñeco, montaje (barra + postes), manos agarradas y recuadro gris "visto desde arriba" que ex_fondos.py:
  - l-sit.gif       (slug l-sit, mode=pose, counter_key=lsit): REPETICIONES. Piernas colgando -> suben rectas -> L -> bajan.
  - l-sit-hold.gif  (slug l-sit-hold, mode=timed, counter_key=lsithold): AGUANTE cronometrado. Piernas colgando (flecha) -> L aguantando (reloj gris).
Como lo mira la app (workout.js: LSitTracker / processLSit / createLSitHoldChecker), de PERFIL con hombro, cadera, rodilla y tobillo del lado que mira:
  - montado en las paralelas: tronco VERTICAL (>= LSIT_MOUNT_TORSO_MIN_TILT_DEG = 55) y brazos ESTIRADOS (codo >= LSIT_ARM_STRAIGHT_DEG = 145),
  - kneeRel = (rodilla.y - cadera.y) / muslo ; ankleRel = (tobillo.y - cadera.y) / (muslo + pantorrilla)   (0 = a la altura de la cadera, 1 = colgando),
  - "L" (arriba): kneeRel y ankleRel entre LSIT_LEG_ABOVE_MIN_REL (-0.34) y LSIT_UP_*_REL (0.77) con la RODILLA ESTIRADA (>= LSIT_KNEE_STRAIGHT_MIN_DEG = 100);
    en el hold ademas vale el angulo hombro-cadera-rodilla <= LSITHOLD_HIP_UP_MAX_DEG (125) -> una L de libro da ~90,
  - "abajo": kneeRel >= LSIT_DOWN_KNEE_REL (0.82) y ankleRel >= LSIT_DOWN_ANKLE_REL (0.88) (piernas colgando del todo).
De perfil las dos barras paralelas se tapan una a otra: el recuadro gris "visto desde arriba" las muestra (dos lineas con las manos encima,
el cuerpo entre ellas). Las manos NO se mueven: se mueven solo las piernas.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_lsit.py [carpeta_salida] [clave=valor ...]   (genera l-sit.gif, l-sit-hold.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 2.6
CFG = dict(hx=0.0, far_dx=-0.05, straight=0.997, tilt=0, post0=-0.65, post1=2.45, margin=0.5, arrows=1, clock=1,
           thD=273, shD=275, footD=-8, thM=305, shM=305, footM=8, thL=4, shL=4, footL=26, gap=4,
           arc_r=2.4, arc_a0=-76, arc_a1=-22, clock_x=1.15, clock_y=1.45, clock_r=0.27,
           inset=1, inset_x=1.85, inset_y=4.25, inset_s=0.85)
# hx: x de las manos (fijas en la barra); far_dx: la mano lejana queda un poco detras (profundidad); straight: fraccion del brazo estirado (1 = recto del todo)
# thX/shX/footX: angulos (matematicos) de muslo, espinilla y pie en D (colgando) / M (a medio camino) / L (piernas rectas a la altura de la cadera)
# gap: grados que la pierna lejana queda por debajo de la cercana (para que se vean las dos piernas)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
LSIT_MOUNT_TORSO_MIN_TILT_DEG = 55
LSIT_ARM_STRAIGHT_DEG = 145
LSIT_KNEE_STRAIGHT_MIN_DEG = 100
LSIT_UP_ANKLE_REL = 0.77
LSIT_UP_KNEE_REL = 0.77
LSIT_LEG_ABOVE_MIN_REL = -0.34
LSIT_DOWN_ANKLE_REL = 0.88
LSIT_DOWN_KNEE_REL = 0.82
LSITHOLD_HIP_UP_MAX_DEG = 125
REACH = L_UA + L_FA

hx = CFG['hx']; hxf = hx + CFG['far_dx']
RIG = [('bar', BAR, CFG['post0'], CFG['post1']), ('post', CFG['post0'], 0.0, BAR), ('post', CFG['post1'], 0.0, BAR)]
SH = (hx + 0.0, BAR + 0.075 + CFG['straight'] * REACH)   # hombro: justo encima de las manos, brazos rectos y verticales


def pose(th, sh, ft):
    g = CFG['gap']; t = CFG['tilt']
    return dict(f=1, ground=False, sh=SH, torso=90 - t, head=90 - t * 0.45,
                near_arm=('ik', (hx, BAR + 0.075), 'cw'), far_arm=('ik', (hxf, BAR + 0.075), 'cw'),
                near_leg=('fk', th, sh, ft), far_leg=('fk', th - g, sh - g, ft))


D = pose(CFG['thD'], CFG['shD'], CFG['footD'])
M = pose(CFG['thM'], CFG['shM'], CFG['footM'])
L = pose(CFG['thL'], CFG['shL'], CFG['footL'])


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
    """Manos agarrando las barras: la barra pasa POR DELANTE del puño y los nudillos asoman por encima (como en fondos)."""
    J = build_side(pose_)
    ex = [lambda pen: pen.line([(CFG['post0'], BAR), (CFG['post1'], BAR)], w=pen.c.LW * 1.3)]   # la barra CERCANA pasa por delante del cuerpo

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


HIP = build_side(L)['H']


def flecha_arco(subiendo):
    """Flecha gris curva alrededor de la cadera: las piernas suben (de colgando a la L) o bajan."""
    def f(pen):
        if not CFG['arrows']:
            return
        a0, a1 = (CFG['arc_a0'], CFG['arc_a1']) if subiendo else (CFG['arc_a1'], CFG['arc_a0'])
        draw_arrow(pen, HIP, CFG['arc_r'], a0, a1)
    return f


def reloj(hand_deg):
    """reloj gris debajo de las piernas (aguante cronometrado): esfera + manecilla larga + corta fija"""
    def draw(pen):
        if not CFG['clock']:
            return
        c = np.array([CFG['clock_x'], CFG['clock_y']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


def vista_cenital():
    """Recuadro gris 'visto desde arriba': las dos lineas son las DOS barras paralelas (de perfil se tapan una a otra), los puntos las manos
    y el circulo la cabeza, entre las barras."""
    k_ = CFG['inset_s']; cx, cy, hw, hh = CFG['inset_x'], CFG['inset_y'], 0.95 * k_, 0.72 * k_
    gap = 0.34 * k_

    def f(pen):
        if not CFG['inset']:
            return
        pen.line([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh), (cx - hw, cy - hh)], w=pen.c.LI * 0.8, col=FLOOR)
        for sg in (1, -1):
            pen.line([(cx - hw + 0.12, cy + sg * gap), (cx + hw - 0.12, cy + sg * gap)], w=pen.c.LW * 0.9)
        hxs = cx - 0.05 * k_
        pen.line([(hxs, cy - gap * 0.78), (hxs, cy + gap * 0.78)], w=pen.c.LW * 0.9)
        pen.paint([('c', (hxs + 0.12 * k_, cy), 0.14 * k_)])
        for sg in (1, -1):
            pen.paint([('c', (hxs, cy + sg * gap), 0.05 * k_)])
    return f


ex = lambda p, extra: [cara(build_side(p))] + manos(p) + extra + [vista_cenital()]
inset_box = (CFG['inset_x'] - 1.0, CFG['inset_y'] - 0.8, CFG['inset_x'] + 1.0, CFG['inset_y'] + 0.8) if CFG['inset'] else None

# ---- repeticiones: colgando -> subiendo (flecha arriba) -> L -> bajando (flecha abajo)
render_scene([D, M, L, M], OUT + 'l-sit', props=RIG, durations=[1200, 700, 1300, 700], margin=CFG['margin'], bbox_extra=inset_box,
             extras=[ex(D, []), ex(M, [flecha_arco(True)]), ex(L, []), ex(M, [flecha_arco(False)])])
# ---- aguante: colgando (flecha arriba) -> L aguantando (reloj) -> L aguantando (reloj avanzado)
render_scene([D, L, L], OUT + 'l-sit-hold', props=RIG, durations=[1300, 1400, 1400], margin=CFG['margin'], bbox_extra=inset_box,
             extras=[ex(D, [flecha_arco(True)]), ex(L, [reloj(90)]), ex(L, [reloj(-10)])])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def medidas(J, sd='near'):
    s, e, w_ = J[sd + '_arm']; hp, k, a = J[sd + '_leg'][:3]
    # en la app la Y de imagen crece hacia ABAJO: aqui y va hacia ARRIBA, asi que (k.y - h.y) de la app = (hp.y - k.y) aqui
    kneeRel = (hp[1] - k[1]) / L_THIGH
    ankleRel = (hp[1] - a[1]) / (L_THIGH + L_SHIN)
    d = J['S'] - J['H']
    tilt = float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))
    return dict(elbow=ang3(s, e, w_), knee=ang3(hp, k, a), hip=ang3(J['S'], hp, k), kr=kneeRel, ar=ankleRel, tilt=tilt)


def suelo(J):
    return min(min(J[sd + '_leg'][2][1], J[sd + '_leg'][3][1], J[sd + '_leg'][4][1]) for sd in ('near', 'far'))


for nombre, P in (('abajo (colgando)', D), ('a medio camino', M), ('L arriba', L)):
    J = build_side(P)
    for sd in ('near', 'far'):
        m = medidas(J, sd)
        print(f"{nombre:17s} {sd:4s}: tronco {m['tilt']:.0f}° | codo {m['elbow']:.0f}° | rodilla {m['knee']:.0f}° | cadera(hombro-cadera-rodilla) {m['hip']:.0f}° | "
              f"kneeRel {m['kr']:+.2f} ankleRel {m['ar']:+.2f}")
    print(f"{'':17s} pie mas bajo a y={suelo(J):.2f}")
    for sd in ('near', 'far'):
        m = medidas(J, sd)
        assert m['tilt'] >= LSIT_MOUNT_TORSO_MIN_TILT_DEG, 'el tronco debe ir vertical (montado)'
        assert m['elbow'] >= LSIT_ARM_STRAIGHT_DEG, 'los brazos deben ir estirados'
        assert m['knee'] >= 150, 'rodillas estiradas'
    assert suelo(J) > 0.15, 'los pies no deben tocar el suelo'

for sd in ('near', 'far'):
    mD, mM, mL = (medidas(build_side(P), sd) for P in (D, M, L))
    assert mD['kr'] >= LSIT_DOWN_KNEE_REL and mD['ar'] >= LSIT_DOWN_ANKLE_REL, 'abajo: las piernas deben colgar del todo'
    assert mL['kr'] <= LSIT_UP_KNEE_REL and mL['ar'] <= LSIT_UP_ANKLE_REL, 'L: las piernas deben subir a la altura de la cadera'
    assert mL['kr'] >= LSIT_LEG_ABOVE_MIN_REL and mL['ar'] >= LSIT_LEG_ABOVE_MIN_REL, 'L: las piernas no deben pasar de la horizontal'
    assert mL['knee'] >= LSIT_KNEE_STRAIGHT_MIN_DEG, 'L: rodillas estiradas'
    assert mL['hip'] <= LSITHOLD_HIP_UP_MAX_DEG, 'L: angulo de cadera plegado (hold)'
    assert not (mM['kr'] >= LSIT_DOWN_KNEE_REL and mM['ar'] >= LSIT_DOWN_ANKLE_REL) and not (mM['kr'] <= LSIT_UP_KNEE_REL and mM['ar'] <= LSIT_UP_ANKLE_REL), \
        'a medio camino no debe ser ni L ni abajo (zona intermedia)'
print('OK: abajo (cuelga), a medio camino (zona intermedia) y L (cuenta) coinciden con los umbrales del contador')
