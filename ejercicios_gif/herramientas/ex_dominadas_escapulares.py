"""Dominadas escapulares (scapular pull-up), vista FRONTAL, colgado de la barra con agarre prono a la anchura de los hombros.
Mismo montaje (barra + postes), muñeco, manos agarradas y vista que ex_dominadas.py / ex_chin_ups.py. Lo que cambia es el movimiento:
  - los BRAZOS SE QUEDAN ESTIRADOS (en la app: codo >= SCAPULARPULL_ELBOW_BENT_MAX_DEG = 130 grados; mas de 3 fotogramas por
    debajo invalidan la repeticion),
  - solo se mueve el omoplato: A) colgado pasivo, hombros encogidos hacia las orejas; B) omoplatos bajados y juntos -> el
    TRONCO sube un poco respecto a las manos (la articulacion del hombro casi no se mueve, el pecho y la cabeza suben),
  - el rango es PEQUEÑO: la cabeza nunca se acerca a la barra (en la app el hombro sube ~0.18 anchos de hombro, umbral
    SCAPULARPULL_MOVE_FACTOR = 0.07),
  - el CUERPO ENTERO sube y baja (tobillos siguen al hombro: SCAPULARPULL_FEET_FOLLOW_MIN_RATIO = 0.5), sin tocar el suelo,
  - la posicion inicial es un DEAD HANG: pies despegados y rodillas dobladas hacia atras (espinillas acortadas por la perspectiva,
    igual que en ex_dominadas.py), que es lo que exige la app para armar la serie (checkDeadHangPosture),
  - flecha gris arriba = "el cuerpo sube" (solo en el fotograma B).
Al final se comprueban los umbrales del contador contra la geometria dibujada.
Uso: python ex_dominadas_escapulares.py [carpeta_salida] [clave=valor ...]   (genera dominadas-escapulares.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
CFG = dict(grip=0.58, reachA=0.998, reachB=0.955, shrugA=0.14, shrugB=-0.07, shin=0.55, head=90, margin=0.5,
           arrow_x=1.02, arrow=1)
# reachA / reachB: fraccion del brazo estirado (1 = recto del todo) colgado / con los omoplatos bajados
# shrugA / shrugB: hombros encogidos (+, hacia las orejas) / bajados (-); la diferencia es lo que sube el tronco
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
SCAPULARPULL_ELBOW_BENT_MAX_DEG = 130
SCAPULARPULL_MOVE_FACTOR = 0.07
SCAPULARPULL_FEET_FOLLOW_MIN_RATIO = 0.5
REACH = L_UA + L_FA
SW = 0.68                     # ancho de hombros dibujado (2 * shoulder_w = 2 * 0.34)

g = CFG['grip']
legs = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268), shin_R=CFG['shin'], shin_L=CFG['shin'])


def pose(hip_y, shrug):
    return dict(view='front', ground=False, hip=(0, hip_y), torso=90, head=CFG['head'], shrug=shrug,
                R_arm=('ik', (g, BAR), 'cw'), L_arm=('ik', (-g, BAR), 'ccw'), **legs)


def hip_for(reach, shrug):
    """cadera que deja el brazo a la fraccion 'reach' de su longitud: hombro = cadera + torso(1) + encogimiento"""
    dy = np.sqrt((reach * REACH) ** 2 - (g - 0.34) ** 2)
    return BAR - dy - 1.0 - shrug


hipA = hip_for(CFG['reachA'], CFG['shrugA'])
hipB = hip_for(CFG['reachB'], CFG['shrugB'])
A = pose(hipA, CFG['shrugA'])       # colgado pasivo, hombros hacia las orejas
B = pose(hipB, CFG['shrugB'])       # omoplatos bajados: el cuerpo entero sube, codos casi rectos


def manos(pose_):
    """Manos agarrando la barra (agarre prono visto de frente), igual que ex_dominadas.py."""
    J = build_front(pose_); hs = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        hs.append(w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05)
    return [lambda pen, h=h: draw_grip_front(pen, h, BAR) for h in hs]


def flechas(pen):
    """flecha gris a cada lado del cuerpo: el tronco sube un poco (los codos no se doblan)"""
    y0 = hipB + 0.05
    for sg in (1, -1):
        draw_line_arrow(pen, (sg * CFG['arrow_x'], y0), (sg * CFG['arrow_x'], y0 + 0.55))


exA, exB = manos(A), manos(B)
if CFG['arrow']:
    exB = exB + [flechas]
render_scene([A, B], OUT + 'dominadas-escapulares', props=RIG, durations=[1200, 1200], margin=CFG['margin'],
             extras=[exA, exB])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def elbow_deg(J, sd):
    s, e, w_ = J[sd + '_arm']
    a, b = s - e, w_ - e
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


JA, JB = build_front(A), build_front(B)
sh_mid = lambda J: (J['R_arm'][0][1] + J['L_arm'][0][1]) / 2
ank = lambda J: (J['R_leg'][2][1] + J['L_leg'][2][1]) / 2
sh_rise = (sh_mid(JB) - sh_mid(JA)) / SW
ank_rise = (ank(JB) - ank(JA)) / SW
head_gap = BAR - (JB['hd'][1] + 0.30)
print(f"codo A={elbow_deg(JA,'R'):.0f} / B={elbow_deg(JB,'R'):.0f} grados (la app exige >= {SCAPULARPULL_ELBOW_BENT_MAX_DEG}): "
      f"{'OK' if min(elbow_deg(JB,'R'), elbow_deg(JB,'L')) >= SCAPULARPULL_ELBOW_BENT_MAX_DEG else 'FALLA'}")
print(f"hombro sube {sh_rise:.3f} anchos de hombro (umbral {SCAPULARPULL_MOVE_FACTOR}): {'OK' if sh_rise >= SCAPULARPULL_MOVE_FACTOR else 'FALLA'}")
print(f"tronco sube {(JB['S'][1]-JA['S'][1])/SW:.2f} anchos; tobillos suben {ank_rise:.2f} anchos -> ratio tobillo/hombro "
      f"{ank_rise/max(sh_rise,1e-9):.2f} (minimo {SCAPULARPULL_FEET_FOLLOW_MIN_RATIO}): "
      f"{'OK' if ank_rise >= SCAPULARPULL_FEET_FOLLOW_MIN_RATIO * sh_rise else 'FALLA'}")
print(f"suelo: tobillo mas bajo en A = {min(JA['R_leg'][2][1], JA['L_leg'][2][1]):.2f} (suelo y=0) -> "
      f"{'pies colgando' if min(JA['R_leg'][2][1], JA['L_leg'][2][1]) > 0.5 else 'TOCA EL SUELO'}")
print(f"cabeza en B a {head_gap:.2f} de la barra (rango pequeño: no debe llegar): {'OK' if head_gap > 0.1 else 'FALLA'}")
