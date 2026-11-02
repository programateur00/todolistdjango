"""Jumping Jacks (saltos de tijera), DE FRENTE. Mismo muñeco, suelo y flechas grises que el resto de GIFs de ejercicios_gif (figura.py).
SIN cara (sin nariz, ojo ni oreja: draw_front solo dibuja un ovalo liso).

Forma (la de siempre): de pie con los pies JUNTOS y los brazos pegados al cuerpo -> se salta abriendo las piernas (algo mas que el ancho de
hombros) mientras los brazos, ESTIRADOS, suben por los lados hasta quedar por encima de la cabeza (las manos casi se juntan) -> se salta de
nuevo cerrando piernas y bajando los brazos. Cada ida y vuelta = 1 repeticion.

Es DE FRENTE a proposito: es la vista que exige el contador de la app (counter_key="jumpingjack", processJumpingJack en workout.js, migracion 0052),
que mide hombros, caderas, muñecas y tobillos en la imagen. Las comprobaciones del final usan esos mismos umbrales (JUMPINGJACK_*) y simulan
su maquina de estados (cerrado -> abierto con brazos arriba -> cerrado = 1 rep).

Fotogramas: cerrado (pies juntos, brazos abajo) -> abriendo (en el aire, flechas grises hacia fuera/arriba) -> abierto (piernas separadas,
brazos arriba) -> cerrando (en el aire, flechas grises hacia dentro/abajo) -> (bucle).
Uso: python ex_jumping_jacks.py [carpeta_salida] [clave=valor ...]   (genera jumping-jacks.gif + PNG de cada fotograma)
Parametros: ax_open (mitad de la separacion de tobillos abierto, defecto 0.68), ax_mid, ax_closed, hop (cuanto se despegan los pies en el aire),
arrows=0, margin, dur*.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(ax_closed=0.15, ax_mid=0.42, ax_open=0.68, hop=0.14, arrows=1, margin=0.62,
           durC=900, durM=350, durO=900)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (JUMPINGJACK_*)
ARMS_UP_MARGIN = 0.15      # muñeca por encima del hombro en >= esto x ancho de hombros = brazos arriba
ARMS_DOWN_MARGIN = 0.1     # muñeca como mucho esto x ancho de hombros por encima del hombro = brazos abajo
LEGS_OPEN_RATIO = 1.6      # tobillos >= esto x ancho de cadera = piernas abiertas
LEGS_CLOSED_RATIO = 1.3    # tobillos <= esto x ancho de cadera = piernas juntas

LEG = L_THIGH + L_SHIN     # 1.87
HIPW = 0.15                # separacion de la cadera al eje (figura.build_front)


def hip_h(ax):
    """altura de la cadera para que las piernas queden casi estiradas con los tobillos en x=±ax"""
    return float(np.sqrt((LEG - 0.004) ** 2 - (ax - HIPW) ** 2))


def pose(ax, arm_r, arm_l, dy=0.0):
    return dict(view='front', hip=(0, hip_h(ax)), torso=90, head=90, dy=dy,
                R_leg=('ik', (ax, 0.0), 'ccw', 1), L_leg=('ik', (-ax, 0.0), 'cw', -1),
                R_arm=('fk',) + arm_r, L_arm=('fk',) + arm_l)


# brazos: (ang. brazo, ang. antebrazo) del lado derecho de la imagen; el izquierdo es el espejo (180 - ang)
DOWN = (279, 274)          # pegados al cuerpo, manos junto a los muslos
MID = (42, 50)             # a medio camino, en diagonal arriba y afuera
UP = (80, 98)              # por encima de la cabeza, casi estirados (ligero arco hacia dentro, las manos quedan sobre la cabeza)
mir = lambda t: (180 - t[0], 180 - t[1])

FRAMES = [pose(CFG['ax_closed'], DOWN, mir(DOWN)),
          pose(CFG['ax_mid'], MID, mir(MID), dy=CFG['hop']),
          pose(CFG['ax_open'], UP, mir(UP)),
          pose(CFG['ax_mid'], MID, mir(MID), dy=CFG['hop'])]


def final_J(fr):
    """el mismo muñeco que acaba pintando render_scene (con el ajuste al suelo)"""
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


def flechas(i):
    """i=1 (abriendo): flechas grises hacia fuera y arriba; i=3 (cerrando): hacia dentro y abajo"""
    if not CFG['arrows'] or i not in (1, 3):
        return None
    J = JF[i]; opening = (i == 1)

    def draw(pen):
        for sd, sg in (('R', 1), ('L', -1)):
            sh, e, w = J[sd + '_arm']
            rad = (w - sh) / (np.linalg.norm(w - sh) + 1e-9)               # direccion hombro -> muñeca
            tan = rot(rad, 90 * sg) * (1 if opening else -1)               # sentido del giro del brazo
            a0 = w + rad * 0.34 + (-tan * 0.12 if opening else tan * 0.12)
            draw_line_arrow(pen, a0, a0 + tan * 0.42)
            hp, kn, an, fd = J[sd + '_leg']                                  # piernas: flecha horizontal a la altura de la rodilla
            yk = kn[1] - 0.05; x0 = an[0] + sg * (0.36 if opening else 0.78)
            dx = sg * 0.38 * (1 if opening else -1)
            draw_line_arrow(pen, (x0, yk), (x0 + dx, yk))
    return [draw]


imgs = render_scene(FRAMES, OUT + 'jumping-jacks', durations=[int(CFG['durC']), int(CFG['durM']), int(CFG['durO']), int(CFG['durM'])],
                    margin=CFG['margin'], extras=[flechas(i) for i in range(4)])


# ---------------------------------------------------------------- comprobacion contra workout.js (processJumpingJack)
def medidas(J):
    sh = {sd: J[sd + '_arm'][0] for sd in 'RL'}; wr = {sd: J[sd + '_arm'][2] for sd in 'RL'}
    hp = {sd: J[sd + '_leg'][0] for sd in 'RL'}; an = {sd: J[sd + '_leg'][2] for sd in 'RL'}
    shoulder_w = abs(sh['R'][0] - sh['L'][0]); hip_w = abs(hp['R'][0] - hp['L'][0]); ankle_w = abs(an['R'][0] - an['L'][0])
    sh_y = (sh['R'][1] + sh['L'][1]) / 2; wr_y = (wr['R'][1] + wr['L'][1]) / 2        # y matematica (arriba = +)
    return dict(
        arms_up=wr_y > sh_y + ARMS_UP_MARGIN * shoulder_w,                              # en la app (y imagen) es wristMidY < shoulderMidY - 0.15*ancho
        arms_down=wr_y < sh_y + ARMS_DOWN_MARGIN * shoulder_w,
        legs_open=ankle_w > hip_w * LEGS_OPEN_RATIO, legs_closed=ankle_w < hip_w * LEGS_CLOSED_RATIO,
        ratio=ankle_w / hip_w, wr_rel=(wr_y - sh_y) / shoulder_w)


M = [medidas(J) for J in JF]
names = ('cerrado', 'abriendo', 'abierto', 'cerrando')
for nm, m in zip(names, M):
    print(f"{nm:9s}| tobillos/cadera {m['ratio']:.2f} ({'abiertas' if m['legs_open'] else 'juntas' if m['legs_closed'] else 'medio'}) | "
          f"muñeca-hombro {m['wr_rel']:+.2f} anchos ({'arriba' if m['arms_up'] else 'abajo' if m['arms_down'] else 'medio'})")
assert M[0]['legs_closed'] and M[0]['arms_down'], 'cerrado: pies juntos (<1.3x cadera) y brazos abajo'
assert M[2]['legs_open'] and M[2]['arms_up'], 'abierto: piernas abiertas (>1.6x cadera) y brazos arriba (>0.15 anchos sobre el hombro)'
# pies planos y apoyados en cerrado/abierto; en el aire (abriendo/cerrando) despegados
for i in (0, 2):
    for sd in 'RL':
        assert abs(JF[i][sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, f'{names[i]}: los pies deben tocar el suelo'
for i in (1, 3):
    assert JF[i]['R_leg'][2][1] > JF[0]['R_leg'][2][1] + 0.05, f'{names[i]}: en el aire los pies despegan del suelo'
# maquina de estados de processJumpingJack: closed -> (piernas abiertas) open -> (arms up visto + piernas juntas) closed = 1 rep
state, arms_seen, reps = 'closed', False, 0
for m in M[1:] + M[:1]:                    # abriendo, abierto, cerrando, cerrado (un ciclo completo)
    if state == 'closed':
        if m['legs_open']:
            state, arms_seen = 'open', m['arms_up']
    else:
        arms_seen = arms_seen or m['arms_up']
        if m['legs_closed']:
            reps += arms_seen; state, arms_seen = 'closed', False
print('repeticiones contadas en un ciclo:', reps)
assert reps == 1, 'un ciclo del GIF debe contar exactamente 1 repeticion'
print('OK: los jumping jacks coinciden con los umbrales del contador (jumpingjack, processJumpingJack)')
