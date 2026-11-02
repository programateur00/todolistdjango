"""Rodillas altas (marcha / carrera en el sitio con las rodillas a la altura de la cadera), DE FRENTE. Mismo muñeco, suelo y flechas grises
que el resto de GIFs de ejercicios_gif (figura.py). SIN cara (sin nariz, ojo ni oreja: draw_front solo dibuja un ovalo liso).

Forma (la de siempre): de pie, erguido, se sube una rodilla hacia el pecho hasta la altura de la cadera (muslo casi horizontal, visto de frente
queda muy escorzado: la rodilla asoma delante de la cadera y la espinilla cuelga) mientras la otra pierna sigue apoyada y recta; se baja y se sube la
otra, sin pausa. Los brazos van doblados ~90 grados y se mueven al reves que las piernas (rodilla izquierda arriba = brazo derecho adelante).
Cada rodilla que sube y vuelve a apoyarse = 1 repeticion (como cuenta la app).

Es DE FRENTE a proposito: es la vista que exige el contador de la app (counter_key="kneeraises", processKneeRaises en workout.js, migracion 0038;
desde 2026-09-19 compara la altura de cada rodilla+tobillo con la de la OTRA pierna). Las comprobaciones del final usan esos mismos umbrales
(KNEERAISE_*) y simulan su maquina de estados (pierna levantada -> apoyada de nuevo = 1 rep).

Fotogramas: rodilla izquierda arriba -> (la izquierda apoya, la derecha sube a medio camino, flecha gris hacia arriba) -> rodilla derecha arriba ->
(la derecha apoya, la izquierda sube a medio camino, flecha gris hacia arriba) -> (bucle). 1 vuelta del GIF = 2 repeticiones (una por pierna).
Uso: python ex_rodillas_altas.py [carpeta_salida] [clave=valor ...]   (genera rodillas-altas.gif + PNG de cada fotograma)
Parametros: up (escorzo del muslo con la rodilla arriba, defecto 0.30: menor = rodilla mas alta), mid (idem a medio camino), stance (apertura de los pies, grados),
arrows=0, margin, durU/durM.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(up=0.30, mid=0.62, stance=4.0, arrows=1, margin=0.5, durU=650, durM=350)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (KNEERAISE_*)
LIFT_FULL = 0.45          # KNEERAISE_LIFT_FULL: diferencia de altura entre piernas (x longitud de pierna) que equivale a bajada = 0
RAISE_ENTER = 0.75        # KNEERAISE_RAISE_ENTER_FRACTION: por debajo = esa pierna esta levantada
RAISE_EXIT = 0.90         # KNEERAISE_RAISE_EXIT_FRACTION: por encima = apoyada (para armar de pie)
REARM_EXIT = 0.80         # KNEERAISE_REARM_EXIT_FRACTION: por encima = apoyada de nuevo (cierra la repeticion en marcha)

LEG = L_THIGH + L_SHIN    # 1.87


# ---- brazos: (ang. brazo, ang. antebrazo, escorzo del brazo, escorzo del antebrazo); el lado derecho de la imagen; el izquierdo es el espejo
FWD = (292, 108, 0.62, 0.52)     # brazo ADELANTE: codo doblado ~90 grados, la mano sube hasta el pecho (escorzado: apunta a la camara)
BACK = (268, 266, 0.42, 1.00)    # brazo ATRAS: el codo va hacia atras (apenas se ve el brazo), el antebrazo cuelga hasta la cadera
MIDA = (282, 100, 0.55, 0.78)    # a medio camino (cambiando de sentido)


def arm(spec, sd):
    a, f = (spec[0], spec[1]) if sd == 'R' else (180 - spec[0], 180 - spec[1])
    return ('fk', a, f)


def pose(L_state, R_state, arms):
    """L_state / R_state: 'down' | 'mid' | 'up' (pierna izquierda / derecha de la IMAGEN). arms = (spec_R, spec_L)"""
    p = dict(view='front', hip=(0, LEG), torso=90, head=90, R_arm=arm(arms[0], 'R'), L_arm=arm(arms[1], 'L'))
    for sd, st, sg in (('R', R_state, 1), ('L', L_state, -1)):
        base = 270 + (CFG['stance'] if sd == 'R' else -CFG['stance'])
        if st == 'down':
            p[sd + '_leg'] = ('fk', base, base, sg)
        else:
            sc = CFG['up'] if st == 'up' else CFG['mid']
            # rodilla delante de la cadera (escorzo del muslo); la espinilla cuelga casi vertical, un pelin hacia fuera (que no se solape con la pierna de apoyo)
            p[sd + '_leg'] = ('fk', base, base, sg)
            p['thigh_' + sd] = sc
            p['shin_' + sd] = 0.96 if st == 'up' else 0.98
    for sd, spec in (('R', arms[0]), ('L', arms[1])):
        p['fore_' + sd + '_ua'] = spec[2]; p['fore_' + sd + '_fa'] = spec[3]
    return p


FRAMES = [pose('up', 'down', (FWD, BACK)),      # rodilla izquierda arriba, brazo derecho adelante
          pose('down', 'mid', (MIDA, MIDA)),    # izquierda apoya, derecha sube
          pose('down', 'up', (BACK, FWD)),      # rodilla derecha arriba, brazo izquierdo adelante
          pose('mid', 'down', (MIDA, MIDA))]    # derecha apoya, izquierda sube


def final_J(fr):
    """el mismo muñeco que acaba pintando render_scene (con el ajuste al suelo)"""
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


def flechas(i):
    """fotogramas 1 y 3 (a medio camino): flecha gris hacia arriba junto a la rodilla que sube"""
    if not CFG['arrows'] or i not in (1, 3):
        return None
    J = JF[i]; sd = 'R' if i == 1 else 'L'; sg = 1 if sd == 'R' else -1

    def draw(pen):
        hp, kn, an, fd = J[sd + '_leg']
        x = kn[0] + sg * 0.46
        draw_line_arrow(pen, (x, kn[1] - 0.48), (x, kn[1] + 0.02))
    return [draw]


def pierna_delante(J, sd, fk):
    """la pierna que sube se pinta POR DELANTE del cuerpo (figura.draw_front pinta las piernas antes que el tronco): de frente el muslo apunta a la camara,
    asi que se ve MUY corto, con la rodilla grande (mas cerca de la camara) y la espinilla colgando debajo. Como en pistol-squat-frente."""
    def f(pen):
        LI = pen.c.LI
        hp, kn, an, fd = J[sd + '_leg']
        sg = 1 if sd == 'R' else -1
        shapes = tube(hp, kn, 0.19, 0.13 * fk, bulge=0.07, peak=0.4) + tube(kn, an, 0.13 * fk, 0.075, bulge=0.2, peak=0.3)
        th = np.linspace(0, 2 * np.pi, 32, endpoint=False)
        fc = an + np.array([fd * 0.05, -0.10])
        shapes.append(('p', np.stack([fc[0] + 0.12 * np.cos(th), fc[1] + 0.08 * np.sin(th)], 1)))
        pen.paint(shapes)
        pen.line(smooth_curve([an + (kn - an) * 0.25 + np.array([sg * 0.02, 0]), an + (kn - an) * 0.55, an + (kn - an) * 0.85]), w=LI * 0.9)   # musculo de la espinilla
        # rótula: dos arcos cortos sobre la rodilla
        pen.line(smooth_curve([kn + np.array([-0.075, 0.03]), kn + np.array([0.0, 0.065]), kn + np.array([0.075, 0.03])]), w=LI * 0.9)
        # pantalon: mitad alta del muslo
        end = hp + (kn - hp) * 0.50
        tv = (end - hp) / (np.linalg.norm(end - hp) + 1e-9); tn = np.array([-tv[1], tv[0]])
        pts = [end + tn * s_ * 0.20 for s_ in (1, -1)] + [hp + 0.21 * np.array([np.cos(a_), np.sin(a_)]) for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False)]
        pen.paint([('p', cv2.convexHull(np.array(pts, np.float32)).reshape(-1, 2))], SHORTS)
        pen.line([end + tn * 0.19, end - tn * 0.19], w=LI * 0.9)
    return f


names = ('izq. arriba', 'dcha. sube', 'dcha. arriba', 'izq. sube')
EXTRAS = [[pierna_delante(JF[0], 'L', 1.25)],
          [pierna_delante(JF[1], 'R', 1.12), flechas(1)[0] if CFG['arrows'] else None],
          [pierna_delante(JF[2], 'R', 1.25)],
          [pierna_delante(JF[3], 'L', 1.12), flechas(3)[0] if CFG['arrows'] else None]]
EXTRAS = [[e for e in ex if e] for ex in EXTRAS]
imgs = render_scene(FRAMES, OUT + 'rodillas-altas', durations=[int(CFG['durU']), int(CFG['durM']), int(CFG['durU']), int(CFG['durM'])],
                    margin=CFG['margin'], extras=EXTRAS)


# ---------------------------------------------------------------- comprobacion contra workout.js (processKneeRaises)
def medidas(J):
    """misma cuenta que el contador: diferencia de altura entre las dos piernas (rodilla + tobillo, promediado) / longitud de pierna.
    En la app las y son de imagen (abajo = +); aqui y matematica (arriba = +), por eso se resta al reves."""
    kn = {sd: J[sd + '_leg'][1] for sd in 'RL'}; an = {sd: J[sd + '_leg'][2] for sd in 'RL'}; hp = {sd: J[sd + '_leg'][0] for sd in 'RL'}
    leg_len = max(np.linalg.norm(an[sd] - hp[sd]) for sd in 'RL')
    diff = ((kn['L'][1] - kn['R'][1]) + (an['L'][1] - an['R'][1])) / 2 / leg_len   # >0: la pierna L va mas alta que la R
    return dict(diff=diff, dropL=1 - diff / LIFT_FULL, dropR=1 + diff / LIFT_FULL,
                kn_rel={sd: (kn[sd][1] - hp[sd][1]) / leg_len for sd in 'RL'})


M = [medidas(J) for J in JF]
for nm, m in zip(names, M):
    print(f"{nm:13s}| bajada_izq {m['dropL']:.2f}  bajada_der {m['dropR']:.2f}  (levantada si < {RAISE_ENTER}; apoyada si >= {REARM_EXIT}) | "
          f"rodilla bajo cadera: izq {-m['kn_rel']['L']:.2f} dcha {-m['kn_rel']['R']:.2f} (x pierna)")

# la pierna que sube debe cruzar el umbral de 'levantada' y la otra seguir apoyada (en los fotogramas con una rodilla arriba)
assert M[0]['dropL'] < RAISE_ENTER and M[0]['dropR'] >= RAISE_EXIT, 'izq. arriba: la izquierda levantada y la derecha apoyada'
assert M[2]['dropR'] < RAISE_ENTER and M[2]['dropL'] >= RAISE_EXIT, 'dcha. arriba: la derecha levantada y la izquierda apoyada'
assert M[1]['dropL'] >= REARM_EXIT and M[3]['dropR'] >= REARM_EXIT, 'la pierna que baja debe contar como apoyada de nuevo'
# la rodilla arriba debe quedar cerca de la altura de la cadera (muslo casi horizontal): bien por encima de la mitad de la pierna
for i, sd in ((0, 'L'), (2, 'R')):
    assert -M[i]['kn_rel'][sd] < 0.25, f'{names[i]}: la rodilla debe quedar casi a la altura de la cadera (muslo ~horizontal)'
# pie de apoyo realmente en el suelo, el otro en el aire
for i, down_sd in ((0, 'R'), (1, 'L'), (2, 'L'), (3, 'R')):
    assert abs(JF[i][down_sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, f'{names[i]}: el pie de apoyo debe tocar el suelo'
# erguido y de frente (frontPositionCheck): tronco vertical, cadera a la misma altura en todos los fotogramas
for J in JF:
    assert abs(J['S'][0] - J['H'][0]) < 1e-6, 'tronco vertical'
assert max(abs(J['H'][1] - JF[0]['H'][1]) for J in JF) < 4e-3, 'la cadera no sube ni baja (marcha en el sitio)'
# maquina de estados de processKneeRaises (armado de pie ya hecho): ninguna levantada -> una levantada -> apoyada de nuevo (dropFraction >= REARM) = +1
side, reps = None, 0
for m in M + M[:1]:     # un ciclo completo y el primer fotograma otra vez (cierra la ultima subida)
    if side is None:
        raisedL, raisedR = m['dropL'] < RAISE_ENTER, m['dropR'] < RAISE_ENTER
        if raisedL or raisedR:
            side = 'L' if (raisedL and (not raisedR or m['dropL'] < m['dropR'])) else 'R'
    else:
        if (m['dropL'] if side == 'L' else m['dropR']) >= REARM_EXIT:
            reps += 1; side = None
print('repeticiones contadas en una vuelta del GIF (un ciclo = una rodilla izq. + una dcha.):', reps)
assert reps == 2, 'una vuelta del GIF debe contar exactamente 2 repeticiones (una por rodilla)'
print('OK: las rodillas altas coinciden con los umbrales del contador (kneeraises, processKneeRaises)')
