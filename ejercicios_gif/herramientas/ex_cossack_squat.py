"""Sentadilla cosaca (Cossack squat), peso corporal, DE FRENTE. Mismo muñeco, suelo y flechas grises que el resto de GIFs de ejercicios_gif.
SIN cara (sin nariz, ojo ni oreja: no se usa cara()).

Forma (Strengthlog, Box Life Magazine, Garage Gym Reviews): pies MUY separados (>= el doble de ancho que los hombros), se baja sobre UNA
pierna (rodilla doblada a fondo, rodilla sobre la punta del pie, pie ENTERO apoyado) mientras la otra queda ESTIRADA hacia el lado con el
TALON en el suelo y las PUNTAS hacia arriba; tronco erguido, manos juntas delante del pecho; se pasa al otro lado (cada lado = 1 repeticion).

Es de FRENTE a proposito: es la vista que exige el contador de la app (counter_key="cossacksquat", processCossackSquat en workout.js,
migracion 0111), que mide SOLO caderas y tobillos en la imagen. Las comprobaciones del final usan esos mismos umbrales (COSSACKSQUAT_*).

Fotogramas: de pie -> bajando a la derecha (flecha gris abajo) -> abajo a la derecha -> paso al centro bajo (flecha gris al otro lado)
-> abajo a la izquierda -> subiendo (flecha gris arriba) -> (bucle).
La cadera recorre un arco alrededor del tobillo de la pierna estirada (que se mantiene recta con el talon fijo en el suelo).
Uso: python ex_cossack_squat.py [carpeta_salida] [clave=valor ...]   (genera cossack-squat.gif + PNG de cada fotograma)
Parametros: stance (mitad de la separacion de tobillos, defecto 1.10), deep / mid (altura de la cadera abajo / intermedia),
low_c (altura de la cadera al pasar por el centro), foot_tilt (grados extra: cuanto mas, mas vertical queda el pie estirado; defecto 20), arrows=0, margin, dur*.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(stance=1.10, deep=0.95, mid=1.30, low_c=1.12, foot_tilt=20.0, arrows=1, margin=0.62,
           arrow_off=0.80, arrow_len=0.55, durA=1000, durM=600, durB=1100, durC=700)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

LEG = L_THIGH + L_SHIN           # 1.87
HIPW = 0.15                      # separacion de la cadera al eje (figura.build_front)
SHW = 0.34                       # semi-ancho de hombros (figura.build_front)
ax = CFG['stance']
HAND = (0.06, 0.78)              # manos juntas delante del pecho: (x a cada lado del centro, altura sobre la cadera)
STRAIGHT = LEG - 0.02            # pierna estirada: casi recta
BEND = {1: 'ccw', -1: 'cw'}      # lado hacia el que se dobla la rodilla (hacia fuera) de la pierna derecha (+1) / izquierda (-1)


def foot_low_rel(ang, sgn):
    """punto mas bajo del pie 'puntas arriba' respecto al tobillo (misma regla que figura.front_shift)"""
    he, to = foot_toesup(np.zeros(2), ang, sgn)
    return foot_poly(np.zeros(2), he, to)[:, 1].min() + 0.01


def legs_and_arms(hx, hy, R_leg, L_leg, **kw):
    return dict(view='front', hip=(hx, hy), torso=90, head=90, R_leg=R_leg, L_leg=L_leg,
                R_arm=('ik', (hx + HAND[0], hy + HAND[1]), 'ccw'), L_arm=('ik', (hx - HAND[0], hy + HAND[1]), 'cw'), **kw)


def pose_even(hy):
    """de pie / paso por el centro: las dos piernas simetricas, pies planos"""
    return legs_and_arms(0.0, hy, ('ik', (ax, 0.0), 'ccw', 1), ('ik', (-ax, 0.0), 'cw', -1))


def pose_side(hy, s):
    """s=+1: se dobla la pierna DERECHA de la imagen (la izquierda queda estirada); s=-1: al reves.
    La pierna estirada se mantiene recta con el talon en el suelo, asi que la cadera sigue un arco alrededor de su tobillo."""
    sg = -s                                         # lado de la pierna estirada (+1 derecha, -1 izquierda)
    ys = 0.0
    for _ in range(4):                              # el pie depende de la inclinacion de la espinilla, y esta de la altura del tobillo
        xoff = float(np.sqrt(STRAIGHT ** 2 - (hy - ys) ** 2))        # distancia horizontal cadera -> tobillo estirado
        jx = sg * ax - sg * xoff                                     # x de la articulacion de la cadera de la pierna estirada
        shin = np.rad2deg(np.arctan2(ys - hy, sg * ax - jx))         # direccion cadera -> tobillo
        fang = shin + (90 + CFG['foot_tilt']) * sg   # pie a 90 grados de la espinilla, puntas hacia arriba y fuera
        ys = -0.17 - foot_low_rel(fang, sg)                          # tobillo a la altura que deja el talon en el mismo suelo que el pie plano
    hx = jx - sg * HIPW                             # centro de la cadera
    bent = ('ik', (s * ax, 0.0), BEND[s], s)
    stra = ('ik', (sg * ax, ys), BEND[sg], sg)
    R, L = (bent, stra) if s == 1 else (stra, bent)
    kw = {('L_footang' if s == 1 else 'R_footang'): float(fang)}
    return legs_and_arms(hx, hy, R, L, **kw)


hs = float(np.sqrt((LEG - 0.004) ** 2 - (ax - HIPW) ** 2))      # cadera de pie
frames = [pose_even(hs), pose_side(CFG['mid'], 1), pose_side(CFG['deep'], 1), pose_even(CFG['low_c']),
          pose_side(CFG['deep'], -1), pose_side(CFG['mid'], -1)]
Jraw = [build_front(f) for f in frames]


def arrow_v(x, y_a, y_b, down):
    def draw(pen):
        yc = (y_a + y_b) / 2 + 0.55
        y0, y1 = (yc + CFG['arrow_len'] / 2, yc - CFG['arrow_len'] / 2)
        if not down:
            y0, y1 = y1, y0
        draw_line_arrow(pen, (x, y0), (x, y1))
    return draw


def arrow_h(y, x_from, x_to):
    return lambda pen: draw_line_arrow(pen, (x_from, y), (x_to, y))


xa = ax + CFG['arrow_off']
ex = None
if CFG['arrows']:
    ex = [None, [arrow_v(xa, hs, CFG['deep'], True)], None, [arrow_h(0.55, CFG['arrow_len'] * 0.6, -CFG['arrow_len'] * 0.6)],
          None, [arrow_v(-xa, hs, CFG['deep'], False)]]

imgs = render_scene(frames, OUT + 'cossack-squat',
                    durations=[int(CFG['durA']), int(CFG['durM']), int(CFG['durB']), int(CFG['durC']), int(CFG['durB']), int(CFG['durM'])],
                    margin=CFG['margin'], extras=ex)
# tira con todos los fotogramas, util para revisar
cv2.imwrite(OUT + 'cossack-squat_todos.png', np.vstack([np.hstack(imgs[:3]), np.hstack(imgs[3:6])]))

# =================================================================== comprobaciones contra el contador (workout.js, COSSACKSQUAT_*)
UMBRAL = dict(ARM_MIN_STANCE=0.50, ARM_MAX_OFFSET=0.30, ARM_MAX_LEG_DIFF=0.20, DROP_DOWN=0.25, BENT_LEG_SHORT=0.78, STRAIGHT_LEG_MIN=0.80,
              ASYMMETRY=0.20, SHIFT_DOWN=0.30, UP_CENTER=0.35, DROP_UP=0.15, LEG_UP=0.85, MIN_STANCE_OF_REF=0.60)


def medidas(J, ref):
    """lo mismo que processCossackSquat, en el plano de la imagen: solo caderas (articulaciones) y tobillos"""
    lH, rH = J['L_leg'][0], J['R_leg'][0]; lA, rA = J['L_leg'][2], J['R_leg'][2]
    legL, legR = np.linalg.norm(lH - lA), np.linalg.norm(rH - rA)
    hipX, hipY = (lH[0] + rH[0]) / 2, (lH[1] + rH[1]) / 2
    midAx = (lA[0] + rA[0]) / 2; sepX = abs(lA[0] - rA[0]); half = sepX / 2
    rL, rR = legL / ref['l'], legR / ref['r']
    drop = (ref['y'] - hipY) / ((ref['l'] + ref['r']) / 2)     # y de la imagen crece hacia abajo; aqui y crece hacia arriba
    bent = 'L' if rL < rR else 'R'
    bentAnkle = lA if bent == 'L' else rA
    shift = np.sign(bentAnkle[0] - midAx) * (hipX - midAx) / half
    return dict(rL=rL, rR=rR, drop=drop, bent=bent, shift=shift, centerOff=abs(hipX - midAx) / half, sepX=sepX,
                bentRatio=min(rL, rR), straightRatio=max(rL, rR), legL=legL, legR=legR, hipY=hipY)


Js = [shift_front(J, front_shift(J)) for J in Jraw]     # igual que render_scene
m0 = medidas(Js[0], dict(l=1, r=1, y=0))                 # solo para calibrar con el fotograma de pie
ref = dict(l=m0['legL'], r=m0['legR'], y=m0['hipY'], sep=m0['sepX'])
M = [medidas(J, ref) for J in Js]
avg = (ref['l'] + ref['r']) / 2
print('separacion de tobillos / ancho de hombros: %.2fx (Box Life: >= 2x)   separacion / largo de pierna: %.2f (armar >= %.2f)'
      % (m0['sepX'] / (2 * SHW), m0['sepX'] / avg, UMBRAL['ARM_MIN_STANCE']))
for i, m in enumerate(M):
    print('fotograma %d: pierna izq %.2f der %.2f | bajada cadera %.2f | desplaz. %.2f | centro %.2f | se dobla: %s'
          % (i + 1, m['rL'], m['rR'], m['drop'], m['shift'], m['centerOff'], m['bent']))
U = UMBRAL
m = M[0]
assert abs(m['legL'] - m['legR']) <= U['ARM_MAX_LEG_DIFF'] * max(m['legL'], m['legR']) and m['sepX'] >= U['ARM_MIN_STANCE'] * avg \
    and m['centerOff'] <= U['ARM_MAX_OFFSET'], 'armar: de pie con los pies muy separados y la cadera centrada'
assert m['centerOff'] <= U['UP_CENTER'] and m['drop'] <= U['DROP_UP'] and min(m['rL'], m['rR']) >= U['LEG_UP'], 'arriba'
for idx, lado in ((2, 'R'), (4, 'L')):
    m = M[idx]
    assert m['bent'] == lado and m['sepX'] >= U['MIN_STANCE_OF_REF'] * ref['sep']
    assert m['drop'] >= U['DROP_DOWN'], 'abajo: la cadera debe bajar >= 25%% del largo de pierna (%.2f)' % m['drop']
    assert m['bentRatio'] <= U['BENT_LEG_SHORT'], 'la pierna que se dobla debe acortarse (%.2f)' % m['bentRatio']
    assert m['straightRatio'] >= U['STRAIGHT_LEG_MIN'], 'la otra debe quedar estirada (%.2f)' % m['straightRatio']
    assert m['straightRatio'] - m['bentRatio'] >= U['ASYMMETRY'] and m['shift'] >= U['SHIFT_DOWN'], 'asimetria / desplazamiento'
for idx in (1, 5):    # fotogramas intermedios: no son "arriba" ni "abajo" del contador (no cambian de estado a la vez)
    m = M[idx]
    assert not (m['centerOff'] <= U['UP_CENTER'] and m['drop'] <= U['DROP_UP']), 'el intermedio no debe contar como arriba'
print('OK: los fotogramas de pie (armar/arriba) y abajo a cada lado pasan los umbrales de processCossackSquat')
