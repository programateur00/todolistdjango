"""Pistol squat (sentadilla a una pierna), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que sentadillas / split squat / plank. Cabeza LISA (plain_head): sin nariz, sin ojo, sin oreja.
Slug del catalogo: pistol-squat (counter_key "pistolsquat", migracion 0092; processPistolSquat en workout.js).
LA APP LO CUENTA DE FRENTE: processPistolSquat mide, solo con caderas y tobillos, el ACORTAMIENTO de cada pierna (distancia cadera->tobillo / su largo
de pie) y la bajada de la cadera (drop), porque de frente no hay angulo de rodilla fiable:
  - ABAJO: drop >= PISTOLSQUAT_DROP_DOWN = 0.30 (largos de pierna), la pierna que trabaja <= PISTOLSQUAT_LEG_SHORT = 0.75 de su largo de pie y asimetria
    entre las dos piernas >= PISTOLSQUAT_ASYMMETRY = 0.18 (la pierna estirada al frente tambien se acorta por escorzo, por eso no basta "una pierna corta"),
  - ARRIBA (cuenta 1 por pierna): drop <= PISTOLSQUAT_DROP_UP = 0.12 y las DOS piernas >= PISTOLSQUAT_LEG_UP = 0.80.
Este GIF va de PERFIL porque es la vista que mejor ENSEÑA el gesto (de frente la pierna estirada apunta a la camara y se ve muy corta). La version de
FRENTE, la que ve el contador y donde si se comprueba la asimetria, es ex_pistol_squat_frente.py -> pistol-squat-frente.gif (las dos valen). Desde el perfil
solo es comprobable lo VERTICAL (la altura de la cadera y de los tobillos no cambia con el punto de vista): el script comprueba el drop y el acortamiento de la
pierna que trabaja.
Forma correcta (Strengthlog, Tom's Guide, MasterClass, Built For Athletes): de pie sobre UNA pierna con la otra ESTIRADA al frente (recta, en el aire,
a la altura de la cadera o algo mas baja, pie en flexion), brazos estirados al frente como contrapeso; se baja sentando la cadera hacia atras y abajo con
el talon de apoyo PLANO en el suelo, la rodilla hacia delante sobre el pie y el tronco inclinado hacia delante (espalda recta, cabeza en linea con la
columna) hasta quedar en cuclillas profundas (cadera por debajo de la rodilla, muslo casi pegado a la pantorrilla) SIN que la pierna estirada toque el
suelo; se sube empujando con el talon hasta estirar la pierna de apoyo.
GIF de 4 fotogramas: de pie (flecha gris abajo) -> bajando -> abajo -> subiendo (flecha gris arriba) -> (vuelta). El pie de apoyo no se mueve.
Uso: python ex_pistol_squat.py [carpeta_salida] [clave=valor ...]   (genera pistol-squat.gif + PNG de cada fotograma; usar una carpeta temporal para probar)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(shinU=270, shinM=257, shinB=246,        # angulo de la espinilla (rodilla->tobillo): 270 = vertical, <270 = rodilla por delante del tobillo
           thighU=270, thighM=325, thighB=20,      # angulo del muslo (cadera->rodilla): 270 = vertical hacia abajo, 0 = horizontal, >0 = rodilla MAS ALTA que la cadera
           torsoU=90, torsoM=70, torsoB=53,        # inclinacion del tronco sobre la horizontal (90 = erguido)
           headU=90, headM=82, headB=74,           # hacia donde apunta la cabeza (en linea con la columna, mirada al frente)
           extU=9, extM=6, extB=4,                 # angulo de la pierna estirada (cadera->pie) sobre la horizontal: la pierna se queda casi horizontal
           foot_ext=38,                            # pie de la pierna estirada respecto a la pierna (flexionado: puntas hacia arriba)
           arm=7, arm_far=12, margin=0.34,          # brazos estirados al frente (0 = horizontal); el lejano un poco distinto para que se vean los dos
           arrows=1, arrow_gap=0.55, arrow_len=0.5,
           durA=1100, durB=600, durC=1200, durD=600)
# shin*/thigh*/torso*/head*/ext*: U = de pie, M = a medio camino, B = abajo
# arrow_gap / arrow_len: separacion de la flecha gris respecto a la espalda (por detras del muñeco) y su largo; arrows=0 las quita
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (bloque PISTOLSQUAT_*)
PISTOLSQUAT_DROP_DOWN = 0.30
PISTOLSQUAT_LEG_SHORT = 0.75
PISTOLSQUAT_DROP_UP = 0.12
PISTOLSQUAT_LEG_UP = 0.80


def hip_rel(shin, thigh):
    """cadera respecto al tobillo de apoyo (en (0,0)) para espinilla y muslo con esos angulos"""
    knee = -dv(shin) * L_SHIN
    return knee - dv(thigh) * L_THIGH


def pose(st):
    shin, thigh, torso, head, ext = (CFG['shin' + st], CFG['thigh' + st], CFG['torso' + st], CFG['head' + st], CFG['ext' + st])
    hip = hip_rel(shin, thigh)
    return dict(f=1, ground=True, plain_head=True, hip=tuple(hip), torso=torso, head=head,
                near_leg=('ik', (0.0, 0.0), 'ccw', 0),                                  # pierna de apoyo (cercana): pie plano, talon en el suelo
                far_leg=('fk', ext, ext, ext + CFG['foot_ext']),                        # pierna estirada (lejana): recta, en el aire, pie flexionado
                near_arm=('fk', CFG['arm'], CFG['arm']), far_arm=('fk', CFG['arm_far'], CFG['arm_far']),
                near_hand=CFG['arm'], far_hand=CFG['arm_far'])


A, M, B = pose('U'), pose('M'), pose('B')
frames = [A, M, B, M]
durs = [CFG['durA'], CFG['durB'], CFG['durC'], CFG['durD']]
JS = [build_side(p_) for p_ in frames]
JSs = [shift_J(J, ground_shift(J)) for J in JS]      # coordenadas con el suelo en y=0 (las mismas que usa render_scene)

# flecha gris POR DETRAS de la espalda (delante van los brazos y la pierna); alto = rango del hombro entre de pie y abajo
xmin = min(all_points(J)[:, 0].min() for J in JSs)
AX = xmin - CFG['arrow_gap'] + 0.25
Y_LO, Y_HI = JSs[2]['S'][1], JSs[0]['S'][1]


def flecha(bajando):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (Y_LO + Y_HI) / 2; h = CFG['arrow_len'] / 2
        a, b = (m + h, m - h) if bajando else (m - h, m + h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


extras = [[flecha(True)], [], [], [flecha(False)]]
bb = (AX - 0.15, 0.0, AX + 0.15, JSs[0]['hd'][1] + 0.3)
imgs = render_scene(frames, OUT + 'pistol-squat', durations=durs, margin=CFG['margin'], bbox_extra=bb, extras=extras)


# ---------------------------------------------------------------- comprobacion
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def knee(J, sd):
    hp, kn, an = J[sd + '_leg'][:3]
    return ang3(hp, kn, an)


nombres = ['de pie', 'bajando', 'abajo']
for n_, J in zip(nombres, JSs[:3]):
    hp, kn, an, he, to = J['near_leg']
    print(f"{n_:8s}: rodilla de apoyo {knee(J, 'near'):5.1f}° | rodilla estirada {knee(J, 'far'):5.1f}° | cadera ({J['H'][0]:+.2f}, {J['H'][1]:.2f}) "
          f"rodilla ({kn[0]:+.2f}, {kn[1]:.2f}) punta x {to[0]:+.2f} | pie estirado: tobillo y {J['far_leg'][2][1]:.2f}, suelo a {min(J['far_leg'][3][1], J['far_leg'][4][1]):.2f} | "
          f"tronco {np.degrees(np.arctan2(*(J['S'] - J['H'])[::-1])):.0f}°")

mU, mM, mB = [knee(J, 'near') for J in JSs[:3]]
assert mU >= 170, f'de pie: la pierna de apoyo casi recta (rodilla {mU:.0f}°)'
assert 100 < mM < 140, f'a medio camino: rodilla entre 100° y 140° ({mM:.0f}°)'
assert mB <= 60, f'abajo: cuclillas profundas, rodilla <= 60° ({mB:.0f}°)'

# --- umbrales del contador (processPistolSquat), medidos en vertical (no dependen del punto de vista)
hipY = [J['H'][1] - J['near_leg'][2][1] for J in JSs]          # altura de la cadera sobre el tobillo de apoyo
LEG = hipY[0]                                                    # largo de la pierna de apoyo de pie (cadera->tobillo)
drops = [(hipY[0] - h) / LEG for h in hipY]
rWork = [h / LEG for h in hipY]                                  # acortamiento de la pierna que trabaja (solo la componente vertical, como de frente)
print(f"drop de la cadera: arriba {drops[0]:.2f} | medio {drops[1]:.2f} | abajo {drops[2]:.2f}  (abajo >= {PISTOLSQUAT_DROP_DOWN}, arriba <= {PISTOLSQUAT_DROP_UP}; datos reales de Alex 0.62-0.66)")
print(f"pierna que trabaja (cadera->tobillo / de pie): arriba {rWork[0]:.2f} | medio {rWork[1]:.2f} | abajo {rWork[2]:.2f}  (abajo <= {PISTOLSQUAT_LEG_SHORT}, arriba >= {PISTOLSQUAT_LEG_UP})")
assert drops[0] <= PISTOLSQUAT_DROP_UP and rWork[0] >= PISTOLSQUAT_LEG_UP, 'arriba: cadera a su altura de pie y pierna de apoyo recuperada'
assert drops[2] >= PISTOLSQUAT_DROP_DOWN + 0.2 and rWork[2] <= PISTOLSQUAT_LEG_SHORT - 0.2, 'abajo: la cadera baja bien por encima de 0.30 y la pierna se acorta bien por debajo de 0.75'
assert PISTOLSQUAT_DROP_UP < drops[1] < PISTOLSQUAT_DROP_DOWN, f'medio: ni abajo ni arriba (drop {drops[1]:.2f}); no cambia de estado'

# --- forma
J0 = JSs[0]
for J in JSs:
    hp, kn, an, he, to = J['near_leg']
    # pie de apoyo: plano, en el suelo, fijo, talon abajo
    assert abs(min(he[1] - 0.04, to[1] - 0.04, an[1] - 0.07)) < 3e-3, 'el pie de apoyo toca el suelo'
    assert abs(he[1] - to[1]) < 1e-6, 'pie de apoyo plano (talon en el suelo, no se levanta)'
    assert abs(an[0] - J0['near_leg'][2][0]) < 2e-3 and abs(to[0] - J0['near_leg'][4][0]) < 2e-3, 'el pie de apoyo no se mueve'
    assert kn[0] > an[0] - 1e-6, 'la rodilla va hacia delante (no hacia dentro de la espinilla)'
    assert kn[0] <= to[0] + 0.15, 'la rodilla pasa algo de la punta (la dorsiflexion lo exige en una pistol) pero sin pasarse mucho'
    # pierna estirada: recta, casi horizontal, hacia delante, en el aire (no toca el suelo ni el muslo de apoyo)
    fh, fk, fa, fhe, fto = J['far_leg']
    assert abs(knee(J, 'far') - 180) < 1e-3, 'pierna estirada recta'
    ext = np.degrees(np.arctan2(fa[1] - fh[1], fa[0] - fh[0]))
    assert 0 <= ext <= 12, f'pierna estirada casi horizontal (hasta 12° por encima de la horizontal; {ext:.1f}°)'
    assert min(fhe[1], fto[1], fa[1]) - 0.04 > 0.30, 'la pierna estirada no toca el suelo (a mas de 0.30 de el)'
    assert fa[0] - fh[0] > 1.7, 'pierna estirada hacia delante'
    # tronco inclinado hacia delante en proporcion a la bajada, cabeza en linea con la columna
    assert abs(J['hdir'] - np.degrees(np.arctan2(*(J['S'] - J['H'])[::-1]))) <= 28, 'cabeza en linea con la columna'
    # brazos estirados al frente (rectos y casi horizontales)
    for sd in ('near', 'far'):
        s_, e_, w_ = J[sd + '_arm']
        assert abs(ang3(s_, e_, w_) - 180) < 1e-3 and abs(np.degrees(np.arctan2(w_[1] - s_[1], w_[0] - s_[0]))) <= 15, 'brazos estirados al frente'
JB = JSs[2]
assert JB['H'][1] <= JB['near_leg'][1][1] - 0.2, 'abajo: la cadera por debajo de la rodilla'
assert JB['H'][1] - 0.20 > 0.05, 'abajo: la cadera no atraviesa el suelo'
assert np.degrees(np.arctan2(*(JB['S'] - JB['H'])[::-1])) <= 55 and JSs[0]['S'][1] - JSs[0]['H'][1] > 0.99, 'tronco: erguido de pie, inclinado abajo'
print(f"OK: pistol squat: rodilla de apoyo {mU:.0f}° / {mM:.0f}° / {mB:.0f}°; drop {drops[2]:.2f} (>= {PISTOLSQUAT_DROP_DOWN}) y pierna de apoyo a {rWork[2]:.2f} de su largo (<= {PISTOLSQUAT_LEG_SHORT}); "
      f"pierna estirada recta y en el aire; pie de apoyo fijo, plano y en el suelo")
