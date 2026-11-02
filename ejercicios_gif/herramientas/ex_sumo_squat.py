"""Sentadilla sumo (sumo squat), peso corporal. Mismo muñeco, suelo y flechas grises que el resto de GIFs de ejercicios_gif.
SIN cara (sin nariz, ojo ni oreja: no se usa cara()).

Dos vistas (parametro perfil=0|1):
  perfil=0 (por defecto)  DE FRENTE -> es la que ENSEÑA el ejercicio: pies MUY separados (~2,5x el ancho de hombros), puntas
                          algo abiertas, rodillas que se abren hacia fuera sobre los pies, tronco erguido, manos juntas
                          delante del pecho; se baja hasta que los muslos quedan ~paralelos al suelo y se sube.
  perfil=1                DE PERFIL, mirando a la derecha -> es la postura que EXIGE el contador de la app (processSquat,
                          counter_key="squat"): mide el angulo cadera-rodilla-tobillo de perfil (arriba >= 160, abajo <= 100)
                          y poniéndose de frente a la camara cierra la serie. De perfil la separacion de los pies no se ve
                          (queda en profundidad), asi que se parece a una sentadilla normal con el tronco mas erguido.
Fotogramas: de pie -> bajando (flecha gris abajo) -> abajo -> subiendo (flecha gris arriba) -> (bucle).
Uso: python ex_sumo_squat.py [carpeta_salida] [clave=valor ...]   (genera sumo-squat[-perfil].gif + PNG de cada fotograma)
Parametros: stance (mitad de la separacion de tobillos, defecto 0.95), deep (altura de cadera abajo), mid (altura intermedia),
arrows=0, margin, dur*.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(perfil=0, stance=0.95, deep=1.12, mid=1.42, arrows=1, margin=0.5, arrow_off=0.62, arrow_len=0.55,
           durA=1000, durM=600, durB=1100,
           # solo perfil
           p_torso_top=84, p_torso_deep=72, p_hip_back=0.62, p_deep=1.02, p_mid=1.42, p_mid_back=0.30)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

LEG = L_THIGH + L_SHIN
HIPW = 0.15            # separacion de la cadera al eje (figura.build_front)
SHW = 0.34             # semi-ancho de hombros (figura.build_front)
ax = CFG['stance']
HAND = (0.06, 0.78)    # manos juntas delante del pecho: (x a cada lado del eje, altura sobre la cadera)


def hip_standing_front():
    return float(np.sqrt((LEG - 0.004) ** 2 - (ax - HIPW) ** 2))


# =================================================================== DE FRENTE
def front(hy):
    return dict(view='front', hip=(0, hy), torso=90, head=90,
                R_leg=('ik', (ax, 0.0), 'ccw', 1), L_leg=('ik', (-ax, 0.0), 'cw', -1),
                R_arm=('ik', (HAND[0], hy + HAND[1]), 'ccw'), L_arm=('ik', (-HAND[0], hy + HAND[1]), 'cw'))


def arrows_front(hy_a, hy_b, down):
    def draw(pen):
        x = ax + CFG['arrow_off'] + 0.1
        yc = (hy_a + hy_b) / 2 + 0.55
        y0, y1 = (yc + CFG['arrow_len'] / 2, yc - CFG['arrow_len'] / 2)
        if not down:
            y0, y1 = y1, y0
        draw_line_arrow(pen, (x, y0), (x, y1))
    return draw


# =================================================================== DE PERFIL
def side(hx, hy, torso):
    # tobillos fijos en x=0, y=0 (antes de apoyar en el suelo); rodillas hacia delante (+x)
    arm_t = (0.42, -0.30)                       # muñeca respecto al hombro: manos juntas delante del pecho
    return dict(view='side', f=1, hip=(hx, hy), torso=torso, head=min(torso + 10, 90),
                near_leg=('ik', (0.0, 0.0), 'ccw', 0), far_leg=('ik', (0.06, 0.0), 'ccw', 0),
                near_arm=('ikr', arm_t, 'cw'), far_arm=('ikr', (arm_t[0] + 0.03, arm_t[1] + 0.02), 'cw'))


def arrows_side(hx_c, hy_c, down):
    def draw(pen):
        x = 1.55
        yc = hy_c + 0.55
        y0, y1 = (yc + CFG['arrow_len'] / 2, yc - CFG['arrow_len'] / 2)
        if not down:
            y0, y1 = y1, y0
        draw_line_arrow(pen, (x, y0), (x, y1))
    return draw


if not CFG['perfil']:
    hs = hip_standing_front(); hd = CFG['deep']; hm = CFG['mid']
    frames = [front(hs), front(hm), front(hd), front(hm)]
    names = 'sumo-squat'
    ex = [None, [arrows_front(hs, hd, True)], None, [arrows_front(hs, hd, False)]] if CFG['arrows'] else None
    props = None
else:
    hs = LEG - 0.004
    frames = [side(0.0, hs, CFG['p_torso_top']),
              side(-CFG['p_mid_back'], CFG['p_mid'], (CFG['p_torso_top'] + CFG['p_torso_deep']) / 2),
              side(-CFG['p_hip_back'], CFG['p_deep'], CFG['p_torso_deep']),
              side(-CFG['p_mid_back'], CFG['p_mid'], (CFG['p_torso_top'] + CFG['p_torso_deep']) / 2)]
    names = 'sumo-squat-perfil'
    ex = [None, [arrows_side(0, hs, True)], None, [arrows_side(0, hs, False)]] if CFG['arrows'] else None
    props = None

imgs = render_scene(frames, OUT + names, props=props, durations=[int(CFG['durA']), int(CFG['durM']), int(CFG['durB']), int(CFG['durM'])],
                    margin=CFG['margin'], extras=ex)

# =================================================================== comprobaciones contra el contador (angulo de rodilla 2D)
def knee_angle_2d(J, sd):
    """angulo cadera-rodilla-tobillo (grados) tal como lo veria la camara (plano de la imagen)"""
    hp, k, a = J[sd + '_leg'][:3]
    u = hp - k; v = a - k
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


if not CFG['perfil']:
    Js = [build_front(f) for f in frames]
    angs = [(knee_angle_2d(J, 'R'), knee_angle_2d(J, 'L')) for J in Js]
    print('angulo de rodilla 2D (D/I) por fotograma:', [f'{a:.0f}/{b:.0f}' for a, b in angs])
    sep = [abs(J['R_leg'][2][0] - J['L_leg'][2][0]) for J in Js]
    print(f'separacion de tobillos / ancho de hombros: {sep[0] / (2 * SHW):.2f}x (sumo: >= 1.5x)')
    print('NOTA: de frente la app cierra la serie (SQUAT_FRONTAL_*): para contar hay que ponerse de perfil.')
else:
    Js = [build_side(f) for f in frames]
    angs = [knee_angle_2d(J, 'near') for J in Js]
    print('angulo de rodilla (cerca) por fotograma:', [f'{a:.0f}' for a in angs])
    assert angs[0] >= 160, 'arriba: la pierna debe superar SQUAT_UP_ANGLE_DEG=160'
    assert angs[2] <= 100, 'abajo: la rodilla debe bajar de SQUAT_DOWN_ANGLE_DEG=100'
    print('OK: arriba >= 160 y abajo <= 100 (processSquat)')
