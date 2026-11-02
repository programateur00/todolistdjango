"""Kneehold Bar (aguante en barra con las rodillas subidas), vista FRONTAL, colgado de la barra con agarre prono a la anchura de los hombros.
Mismo montaje (barra + postes), muñeco, manos agarradas y vista que ex_dominadas.py / ex_dead_hang.py / ex_toes_to_bar.py.
Es un ejercicio ISOMETRICO cronometrado (slug kneehold-bar, mode=timed, counter_key=kneeholdbar), asi que no se cuentan repeticiones:
  - colgado de la barra con los BRAZOS ESTIRADOS (muñecas por encima de los hombros, checkKneeHoldBarPosture),
  - se DOBLAN las rodillas y se SUBEN hasta dejarlas mas o menos a la ALTURA DE LA CADERA (kneeHipGap = (rodilla.y - cadera.y) / ancho de
    hombros <= KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR = 0.4). De frente los muslos apuntan hacia la camara: se ven muy ACORTADOS (las rodillas
    quedan delante del vientre) y las espinillas CUELGAN hacia abajo desde la rodilla (rodilla doblada, no pegada al muslo),
  - se AGUANTA: entre un fotograma y otro solo cambia la manecilla del reloj gris (= "aguanta el tiempo"; en la app la cuenta atras por
    defecto son 30 s). Poner clock=0 para quitarlo.
GIF de 3 fotogramas: colgado con las piernas estiradas (flechas grises hacia arriba = sube las rodillas) -> rodillas arriba aguantando
(reloj) -> rodillas arriba aguantando (reloj avanzado).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_kneehold_bar.py [carpeta_salida] [clave=valor ...]   (genera kneehold-bar.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
CFG = dict(grip=0.58, reach=0.998, shrugA=0.14, shrugB=0.05, spreadA=2, shinA=0.55, thighB=0.20, openB=22, shinB=0.93, kneeGap=0.10,
           margin=0.5, arrow_x=1.02, knee_r=0.165, arrows=1, clock=1, clock_x=0.9, clock_r=0.27)
# grip: mitad de la separacion de las manos (0.58 = un poco mas ancha que los hombros, igual que dead hang / toes to bar)
# reach: fraccion del brazo estirado (1 = recto del todo); shrugA / shrugB: hombros hacia las orejas (+) colgado / aguantando
# spreadA: apertura de las piernas colgando (grados); shinA: acortamiento de la espinilla colgado (rodillas algo flexionadas hacia atras, como dead hang: los pies no tocan el suelo)
# thighB: acortamiento del muslo al subir las rodillas (el muslo apunta hacia la camara); openB: grados que se abren las rodillas hacia fuera; shinB: espinilla colgando (1 = entera)
# kneeGap: cuanto quedan las rodillas POR DEBAJO de la cadera en el dibujo (en torsos; 0 = a la altura de la cadera)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (checkKneeHoldBarPosture)
HANG_MARGIN_FACTOR = 0.08                  # muñecas por encima de los hombros (en anchos de hombro)
KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR = 0.4  # rodilla como mucho 0.4 anchos de hombro POR DEBAJO de la cadera
REACH = L_UA + L_FA
SW = 0.68                                  # ancho de hombros dibujado (2 * shoulder_w = 2 * 0.34)
g = CFG['grip']


def hip_for(reach, shrug):
    """cadera que deja el brazo a la fraccion 'reach' de su longitud: hombro = cadera + torso(1) + encogimiento"""
    dy = np.sqrt((reach * REACH) ** 2 - (g - 0.34) ** 2)
    return BAR - dy - 1.0 - shrug


HIP_A = hip_for(CFG['reach'], CFG['shrugA'])
HIP_B = hip_for(CFG['reach'], CFG['shrugB'])


def pose_A():
    s = CFG['spreadA']
    return dict(view='front', ground=False, hip=(0, HIP_A), torso=90, head=90, shrug=CFG['shrugA'],
                R_arm=('ik', (g, BAR), 'cw'), L_arm=('ik', (-g, BAR), 'ccw'),
                R_leg=('fk', 270 + s, 270 + s), L_leg=('fk', 270 - s, 270 - s), shin_R=CFG['shinA'], shin_L=CFG['shinA'])


def pose_B():
    """rodillas arriba: el muslo (hacia la camara) se ve casi un punto; el 'thigh_*' es lo que mide la caida de la rodilla bajo la cadera"""
    o = CFG['openB']
    return dict(view='front', ground=False, hip=(0, HIP_B), torso=90, head=90, shrug=CFG['shrugB'],
                R_arm=('ik', (g, BAR), 'cw'), L_arm=('ik', (-g, BAR), 'ccw'),
                R_leg=('fk', 270 + o, 270 + o * 0.15), L_leg=('fk', 270 - o, 270 - o * 0.15),
                thigh_R=CFG['kneeGap'] / L_THIGH, thigh_L=CFG['kneeGap'] / L_THIGH, shin_R=CFG['shinB'], shin_L=CFG['shinB'])


A, B = pose_A(), pose_B()


# ---------------------------------------------------------------- extras de dibujo
def manos(pose_):
    """Manos agarrando la barra (agarre prono visto de frente), igual que ex_dominadas.py."""
    J = build_front(pose_); hs = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        hs.append(w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05)
    return [lambda pen, h=h: draw_grip_front(pen, h, BAR) for h in hs]


def piernas_arriba(pose_):
    """Rodillas subidas, vistas de frente: los muslos vienen HACIA la camara (figura.draw_front pinta las piernas primero y el tronco
    encima), asi que se repintan DESPUES del cuerpo: espinilla colgando (detras de la rodilla) con la zapatilla al final, muslo en
    escorzo cubierto por el pantalon y la rodilla redonda, mas grande por estar mas cerca de la camara, delante del vientre."""
    J = build_front(pose_)

    def f(pen):
        LI = pen.c.LI
        for sd in 'RL':
            hp, kn, an, fd = J[sd + '_leg']
            sg = 1 if sd == 'R' else -1
            # espinilla + zapatilla
            shapes = tube(kn, an, 0.15, 0.075, bulge=0.2, peak=0.3)
            fc = an + np.array([sg * 0.03, -0.10])
            th = np.linspace(0, 2 * np.pi, 28, endpoint=False)
            shapes.append(('p', np.stack([fc[0] + 0.12 * np.cos(th) + sg * 0.04, fc[1] + 0.08 * np.sin(th)], 1)))
            pen.paint(shapes)
            pen.line(smooth_curve([kn + (an - kn) * 0.30, kn + (an - kn) * 0.55, kn + (an - kn) * 0.85]), w=LI * 0.9)
        for sd in 'RL':                                                    # muslos con el pantalon (gris) y rodillas delante
            hp, kn, an, fd = J[sd + '_leg']
            pen.paint(tube(hp, kn, 0.20, 0.19, bulge=0.0), SHORTS)
        for sd in 'RL':
            hp, kn, an, fd = J[sd + '_leg']
            sg = 1 if sd == 'R' else -1
            pen.paint([('c', kn + np.array([0.0, -0.035]), CFG['knee_r'])])
            c = kn + np.array([0.0, -0.035])
            pen.line(smooth_curve([c + np.array([-0.065, -0.01]), c + np.array([0.0, 0.045]), c + np.array([0.065, -0.01])]), w=LI * 0.9)   # rotula
    return f


def flechas_arriba():
    """Flechas grises a cada lado del cuerpo: las rodillas suben."""
    def f(pen):
        if not CFG['arrows']:
            return
        y0 = HIP_A - 0.55
        for sg in (1, -1):
            draw_line_arrow(pen, (sg * CFG['arrow_x'], y0), (sg * CFG['arrow_x'], y0 + 0.75))
    return f


def reloj(hand_deg):
    """reloj gris a un lado del cuerpo (aguante cronometrado): esfera + manecilla larga + corta fija"""
    def draw(pen):
        c = np.array([CFG['clock_x'], HIP_B + 0.55]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


exA = manos(A) + [flechas_arriba()]
exB1 = [piernas_arriba(B)] + manos(B) + ([reloj(90)] if CFG['clock'] else [])
exB2 = [piernas_arriba(B)] + manos(B) + ([reloj(-10)] if CFG['clock'] else [])
render_scene([A, B, B], OUT + 'kneehold-bar', props=RIG, durations=[1300, 1400, 1400], margin=CFG['margin'], extras=[exA, exB1, exB2])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def elbow_deg(J, sd):
    s, e, w_ = J[sd + '_arm']
    a, b = s - e, w_ - e
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


for name, P in (('A colgado', A), ('B rodillas arriba', B)):
    J = build_front(P)
    sh_y = (J['R_arm'][0][1] + J['L_arm'][0][1]) / 2
    wr_y = (J['R_arm'][2][1] + J['L_arm'][2][1]) / 2
    hang = (wr_y - sh_y) / SW
    hip_y = J['H'][1]
    knee_y = (J['R_leg'][1][1] + J['L_leg'][1][1]) / 2
    gap = (hip_y - knee_y) / SW          # en la imagen Y crece hacia abajo; aqui y va hacia ARRIBA, asi que la rodilla bajo la cadera = hip_y - knee_y > 0
    low_ank = min(J['R_leg'][2][1], J['L_leg'][2][1])
    estado = 'cuenta (rodillas a la altura de la cadera)' if gap <= KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR else 'NO cuenta (rodillas demasiado bajas)'
    print(f"[{name}] muñecas sobre hombros {hang:.2f} anchos (la app exige > {HANG_MARGIN_FACTOR}); codos {elbow_deg(J,'R'):.0f}/{elbow_deg(J,'L'):.0f}°; "
          f"rodillas {gap:.2f} anchos de hombro bajo la cadera (max {KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR}) -> {estado}; tobillo mas bajo en y={low_ank:.2f}")
    assert hang > HANG_MARGIN_FACTOR, 'las muñecas deben quedar por encima de los hombros (colgado)'
    assert low_ank > 0.5, 'los pies tocan el suelo'
    if name.startswith('B'):
        assert gap <= KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR, 'rodillas demasiado bajas para el contador'
        assert gap > -0.1, 'las rodillas no deben quedar mucho mas altas que la cadera en el dibujo'
    else:
        assert gap > KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR, 'colgado con las piernas estiradas NO debe contar como rodillas arriba'
print('OK: colgado (no cuenta) y rodillas arriba (cuenta) coinciden con los umbrales del contador')
