"""Dead Hang (aguante en barra), vista FRONTAL, colgado de la barra con agarre prono a la anchura de los hombros.
Mismo montaje (barra + postes), muñeco, manos agarradas y vista que ex_dominadas.py / ex_dominadas_escapulares.py.
Es un ejercicio ISOMETRICO cronometrado (mode=timed, counter_key=deadhang), asi que el cuerpo NO se mueve:
  - los BRAZOS van totalmente ESTIRADOS y los hombros relajados hacia las orejas (colgado pasivo),
  - los PIES NO tocan el suelo y las RODILLAS SE DOBLAN HACIA ATRAS: de frente las espinillas se ven acortadas (es lo que exige
    la app, checkDeadHangPosture: espinilla/muslo < DEADHANG_SHIN_THIGH_RATIO_MAX = 0.6 en las DOS piernas; con las piernas
    rectas y los tobillos a la vista NO cuenta),
  - entre un fotograma y otro solo cambia un leve balanceo de las piernas y la manecilla del reloj gris (= "aguanta el
    tiempo"; en la app la cuenta atras por defecto son 30 s). Poner clock=0 para quitar el reloj.
Al final se comprueban los umbrales de la app contra la geometria dibujada.
Uso: python ex_dead_hang.py [carpeta_salida] [clave=valor ...]   (genera dead-hang.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
CFG = dict(grip=0.58, reach=0.998, shrug=0.14, shinA=0.55, shinB=0.50, swayB=3, head=90, margin=0.5,
           clock=1, clock_x=0.9, clock_r=0.27)
# reach: fraccion del brazo estirado (1 = recto del todo); shrug: hombros hacia las orejas (+) = colgado pasivo
# shinA / shinB: acortamiento de la espinilla (rodilla doblada hacia atras, vista de frente); swayB: grados de balanceo en B
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (checkDeadHangPosture)
HANG_MARGIN_FACTOR = 0.08                 # muñecas por encima de los hombros (en anchos de hombro)
DEADHANG_SHIN_THIGH_RATIO_MAX = 0.6       # al ARMAR: espinilla/muslo por debajo = doblada (recta ~0.9-1.1)
DEADHANG_KNEE_BENT_MAX_DEG = 135          # o angulo cadera-rodilla-tobillo cerrado
REACH = L_UA + L_FA
SW = 0.68                                 # ancho de hombros dibujado (2 * shoulder_w = 2 * 0.34)
g = CFG['grip']


def hip_for(reach, shrug):
    """cadera que deja el brazo a la fraccion 'reach' de su longitud: hombro = cadera + torso(1) + encogimiento"""
    dy = np.sqrt((reach * REACH) ** 2 - (g - 0.34) ** 2)
    return BAR - dy - 1.0 - shrug


HIP = hip_for(CFG['reach'], CFG['shrug'])


def pose(shin, sway=0):
    return dict(view='front', ground=False, hip=(0, HIP), torso=90, head=CFG['head'], shrug=CFG['shrug'],
                R_arm=('ik', (g, BAR), 'cw'), L_arm=('ik', (-g, BAR), 'ccw'),
                R_leg=('fk', 272 + sway, 272 + sway), L_leg=('fk', 268 - sway, 268 - sway), shin_R=shin, shin_L=shin)


A = pose(CFG['shinA'])                          # colgado pasivo, rodillas dobladas hacia atras
B = pose(CFG['shinB'], CFG['swayB'])            # igual, con un leve balanceo de piernas


def manos(pose_):
    """Manos agarrando la barra (agarre prono visto de frente), igual que ex_dominadas.py."""
    J = build_front(pose_); hs = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        hs.append(w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05)
    return [lambda pen, h=h: draw_grip_front(pen, h, BAR) for h in hs]


def reloj(hand_deg):
    """reloj gris a un lado del cuerpo (aguante cronometrado): esfera + manecilla larga + corta fija"""
    def draw(pen):
        c = np.array([CFG['clock_x'], HIP + 0.55]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


exA, exB = manos(A), manos(B)
if CFG['clock']:
    exA = exA + [reloj(90)]
    exB = exB + [reloj(-10)]
render_scene([A, B], OUT + 'dead-hang', props=RIG, durations=[1500, 1500], margin=CFG['margin'], extras=[exA, exB])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def elbow_deg(J, sd):
    s, e, w_ = J[sd + '_arm']
    a, b = s - e, w_ - e
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


def knee_deg(J, sd):
    hp, k, a, _ = J[sd + '_leg']
    u, v = hp - k, a - k
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def shin_thigh(J, sd):
    hp, k, a, _ = J[sd + '_leg']
    return float(np.linalg.norm(a - k) / np.linalg.norm(k - hp))


for name, P in (('A', A), ('B', B)):
    J = build_front(P)
    sh_y = (J['R_arm'][0][1] + J['L_arm'][0][1]) / 2
    wr_y = (J['R_arm'][2][1] + J['L_arm'][2][1]) / 2
    margin_w = (wr_y - sh_y) / SW
    ratios = [shin_thigh(J, 'R'), shin_thigh(J, 'L')]
    kdeg = [knee_deg(J, 'R'), knee_deg(J, 'L')]
    low_ank = min(J['R_leg'][2][1], J['L_leg'][2][1])
    print(f"[{name}] muñecas sobre hombros {margin_w:.2f} anchos (la app exige > {HANG_MARGIN_FACTOR}): "
          f"{'OK' if margin_w > HANG_MARGIN_FACTOR else 'FALLA'}")
    print(f"[{name}] codos {elbow_deg(J,'R'):.0f}/{elbow_deg(J,'L'):.0f} grados (brazos estirados)")
    print(f"[{name}] espinilla/muslo {ratios[0]:.2f}/{ratios[1]:.2f} (la app exige < {DEADHANG_SHIN_THIGH_RATIO_MAX} en las dos): "
          f"{'OK' if max(ratios) < DEADHANG_SHIN_THIGH_RATIO_MAX else 'FALLA'}  | angulo rodilla {kdeg[0]:.0f}/{kdeg[1]:.0f} "
          f"(alternativa: <= {DEADHANG_KNEE_BENT_MAX_DEG})")
    print(f"[{name}] tobillo mas bajo en y={low_ank:.2f} (suelo y=0): {'pies colgando' if low_ank > 0.5 else 'TOCA EL SUELO'}")
