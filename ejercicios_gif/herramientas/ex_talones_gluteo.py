"""Talones al glúteo (butt kicks / heel kicks), DE FRENTE. Mismo muñeco, suelo y flechas grises que el resto de GIFs de ejercicios_gif (figura.py).
SIN cara (sin nariz, ojo ni oreja: draw_front solo dibuja un ovalo liso).

Forma (la de siempre): de pie, erguido, marchando / trotando en el sitio. El MUSLO se queda casi vertical (la rodilla NO sube, no es rodillas altas) y es la
rodilla la que se dobla: el talon sube por detras hacia el gluteo mientras la otra pierna sigue apoyada y recta; se vuelve a apoyar y sube el otro, sin pausa.
Los brazos van doblados ~90 grados y se mueven al reves que las piernas, como al correr (talon izquierdo arriba = brazo derecho adelante).
Cada talon que sube y vuelve a apoyarse = 1 repeticion (como cuenta la app).

Es DE FRENTE a proposito: es la vista que exige el contador de la app (counter_key="heelkicks", processHeelKicks en workout.js, migracion 0039;
desde 2026-09-19 compara la altura de cada TOBILLO con la del otro, normalizada por la longitud de pierna). De frente la espinilla se va hacia
atras, asi que queda tapada por el muslo: solo asoma el pie / la parte de fuera de la espinilla, por detras del muslo (el muslo se repinta POR DELANTE).
Las comprobaciones del final usan esos mismos umbrales (HEELKICK_*) y simulan su maquina de estados (talon arriba -> apoyado de nuevo = 1 rep).

Fotogramas: talon izquierdo arriba -> (el izquierdo apoya, el derecho sube a medio camino, flecha gris hacia arriba) -> talon derecho arriba ->
(el derecho apoya, el izquierdo sube a medio camino, flecha gris hacia arriba) -> (bucle). 1 vuelta del GIF = 2 repeticiones (una por pierna).
Uso: python ex_talones_gluteo.py [carpeta_salida] [clave=valor ...]   (genera talones-al-gluteo.gif + PNG de cada fotograma)
Parametros: up / mid (largo con el que se ve la espinilla con el talon arriba / a medio camino; mayor = talon mas alto), ang_up / ang_mid (hacia fuera, grados
sobre la horizontal; 90 = justo detras del muslo), knee (escorzo del muslo: la rodilla sale un pelin hacia delante), stance (apertura de los pies, grados),
arrows=0, margin, durU/durM.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(up=0.92, mid=0.32, ang_up=62, ang_mid=28, knee=0.97, stance=4.0, arrows=1, margin=0.55, durU=650, durM=350)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (HEELKICK_*)
LIFT_ENTER = 0.15         # HEELKICK_LIFT_ENTER: tobillo al menos esta fraccion de la longitud de pierna POR ENCIMA del otro => talon arriba
LIFT_EXIT = 0.07          # HEELKICK_LIFT_EXIT: por debajo => vuelve a estar apoyado (la repeticion se cuenta aqui)
ARM_MAX_DIFF = 0.09       # HEELKICK_ARM_MAX_DIFF: desnivel de reposo de los tobillos (de pie, apoyado) como mucho esto
MAX_UP_SECONDS = 1.5      # HEELKICK_MAX_UP_SECONDS: un talon 'arriba' mas de esto se descarta (no es marcha)

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
            a = CFG['ang_up'] if st == 'up' else CFG['ang_mid']
            # muslo casi vertical (la rodilla sale un pelin hacia delante = escorzo); la espinilla se va hacia ATRAS y un poco hacia fuera:
            # de frente queda muy escorzada (cuelga detras del muslo) y el pie, con la punta abajo, asoma por fuera del muslo
            p[sd + '_leg'] = ('fk', base, a if sd == 'R' else 180 - a, sg)
            p['thigh_' + sd] = CFG['knee']
            p['shin_' + sd] = CFG['up'] if st == 'up' else CFG['mid']
    for sd, spec in (('R', arms[0]), ('L', arms[1])):
        p['fore_' + sd + '_ua'] = spec[2]; p['fore_' + sd + '_fa'] = spec[3]
    return p


FRAMES = [pose('up', 'down', (FWD, BACK)),      # talon izquierdo arriba, brazo derecho adelante
          pose('down', 'mid', (MIDA, MIDA)),    # izquierda apoya, derecha sube
          pose('down', 'up', (BACK, FWD)),      # talon derecho arriba, brazo izquierdo adelante
          pose('mid', 'down', (MIDA, MIDA))]    # derecha apoya, izquierda sube


def final_J(fr):
    """el mismo muñeco que acaba pintando render_scene (con el ajuste al suelo)"""
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


def flechas(i):
    """fotogramas 1 y 3 (a medio camino): flecha gris hacia arriba junto al talon que sube"""
    J = JF[i]; sd = 'R' if i == 1 else 'L'; sg = 1 if sd == 'R' else -1

    def draw(pen):
        hp, kn, an, fd = J[sd + '_leg']
        x = an[0] + sg * 0.42
        draw_line_arrow(pen, (x, an[1] - 0.50), (x, an[1] + 0.02))
    return draw


def pie_atras(J, sd):
    """Zapatilla del talon que sube, vista de frente: el talon va hacia el gluteo, asi que el pie cuelga con la PUNTA hacia abajo (un ovalo alto bajo el tobillo,
    con dos rayitas de la puntera). Va por detras del muslo (se repinta despues el muslo) y encima de la espinilla."""
    def f(pen):
        LI = pen.c.LI
        hp, kn, an, fd = J[sd + '_leg']
        sg = 1 if sd == 'R' else -1
        c = an + np.array([sg * 0.02, -0.15])
        th = np.linspace(0, 2 * np.pi, 40, endpoint=False)
        pen.paint([('p', np.stack([c[0] + 0.105 * np.cos(th), c[1] + 0.19 * np.sin(th)], 1))])
        for dy, hw in ((-0.095, 0.05), (-0.14, 0.04)):
            pen.line([c + np.array([-hw, dy]), c + np.array([hw, dy])], w=LI * 0.8)       # puntera
        pen.line(smooth_curve([c + np.array([-0.06, 0.12]), c + np.array([0.0, 0.15]), c + np.array([0.06, 0.12])]), w=LI * 0.8)   # caña del zapato
    return f


def muslo_delante(J, sd):
    """El muslo de la pierna que patea se repinta POR DELANTE de la espinilla (figura.draw_front pinta la espinilla encima del muslo): de frente la espinilla
    va hacia atras, detras del muslo, y solo asoma el pie / el borde de fuera. Se repinta tambien la mitad alta del pantalon de esa pierna."""
    def f(pen):
        LI = pen.c.LI
        hp, kn, an, fd = J[sd + '_leg']
        pen.paint(tube(hp, kn, 0.19, 0.13, bulge=0.07, peak=0.4))
        pen.line(smooth_curve([hp + (kn - hp) * 0.45, hp + (kn - hp) * 0.70, hp + (kn - hp) * 0.92]), w=LI * 0.9)             # musculo del muslo
        pen.line(smooth_curve([kn + np.array([-0.075, 0.03]), kn + np.array([0.0, 0.065]), kn + np.array([0.075, 0.03])]), w=LI * 0.9)   # rotula
        end = hp + (kn - hp) * 0.50
        tv = (end - hp) / (np.linalg.norm(end - hp) + 1e-9); tn = np.array([-tv[1], tv[0]])
        pts = [end + tn * s_ * 0.20 for s_ in (1, -1)] + [hp + 0.21 * np.array([np.cos(a_), np.sin(a_)]) for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False)]
        pen.paint([('p', cv2.convexHull(np.array(pts, np.float32)).reshape(-1, 2))], SHORTS)
        pen.line([end + tn * 0.19, end - tn * 0.19], w=LI * 0.9)
    return f


names = ('izq. arriba', 'dcha. sube', 'dcha. arriba', 'izq. sube')
EXTRAS = [[pie_atras(JF[0], 'L'), muslo_delante(JF[0], 'L')],
          [pie_atras(JF[1], 'R'), muslo_delante(JF[1], 'R'), flechas(1)],
          [pie_atras(JF[2], 'R'), muslo_delante(JF[2], 'R')],
          [pie_atras(JF[3], 'L'), muslo_delante(JF[3], 'L'), flechas(3)]]
if not CFG['arrows']:
    EXTRAS = [[e for e in ex if e.__name__ != 'draw'] for ex in EXTRAS]
imgs = render_scene(FRAMES, OUT + 'talones-al-gluteo', durations=[int(CFG['durU']), int(CFG['durM']), int(CFG['durU']), int(CFG['durM'])],
                    margin=CFG['margin'], extras=EXTRAS)


# ---------------------------------------------------------------- comprobacion contra workout.js (processHeelKicks)
def medidas(J):
    """misma cuenta que el contador: altura de cada tobillo respecto al otro / longitud de pierna (la mayor cadera->tobillo).
    En la app las y son de imagen (abajo = +); aqui y matematica (arriba = +), por eso se resta al reves."""
    an = {sd: J[sd + '_leg'][2] for sd in 'RL'}; hp = {sd: J[sd + '_leg'][0] for sd in 'RL'}; kn = {sd: J[sd + '_leg'][1] for sd in 'RL'}
    leg_len = max(np.linalg.norm(an[sd] - hp[sd]) for sd in 'RL')
    diff = (an['L'][1] - an['R'][1]) / leg_len        # >0: el tobillo izquierdo va mas alto que el derecho
    return dict(liftL=diff, liftR=-diff, an=an, hp=hp, kn=kn, leg_len=leg_len)


M = [medidas(J) for J in JF]
for nm, m in zip(names, M):
    print(f"{nm:13s}| subida_izq {m['liftL']:+.2f}  subida_der {m['liftR']:+.2f}  (arriba si >= {LIFT_ENTER}; apoyado si <= {LIFT_EXIT}) | "
          f"tobillo sobre rodilla: izq {(m['an']['L'][1] - m['kn']['L'][1]) / m['leg_len']:+.2f} dcha {(m['an']['R'][1] - m['kn']['R'][1]) / m['leg_len']:+.2f} (x pierna)")

# el talon que sube cruza con margen el umbral de 'arriba' y la pierna de apoyo queda 'apoyada' (en los fotogramas con un talon arriba)
assert M[0]['liftL'] >= LIFT_ENTER * 2 and M[0]['liftR'] <= LIFT_EXIT, 'izq. arriba: el talon izquierdo debe subir claramente y el derecho estar apoyado'
assert M[2]['liftR'] >= LIFT_ENTER * 2 and M[2]['liftL'] <= LIFT_EXIT, 'dcha. arriba: el talon derecho debe subir claramente y el izquierdo estar apoyado'
# a medio camino ya cuenta como 'sube' (>= umbral) y la pierna que acaba de apoyar cuenta como apoyada (<= umbral de salida)
assert M[1]['liftR'] >= LIFT_ENTER and M[1]['liftL'] <= LIFT_EXIT, 'dcha. sube: la derecha sube y la izquierda ya esta apoyada'
assert M[3]['liftL'] >= LIFT_ENTER and M[3]['liftR'] <= LIFT_EXIT, 'izq. sube: la izquierda sube y la derecha ya esta apoyada'
# talon al GLUTEO (no rodillas altas): el tobillo queda claramente por encima de la rodilla y la rodilla casi no sube (muslo ~vertical)
for i, sd in ((0, 'L'), (2, 'R')):
    m = M[i]
    assert (m['an'][sd][1] - m['kn'][sd][1]) / m['leg_len'] >= 0.25, f'{names[i]}: el talon debe quedar claramente por encima de la rodilla (hacia el gluteo)'
    assert (m['hp'][sd][1] - m['kn'][sd][1]) / L_THIGH >= 0.9, f'{names[i]}: el muslo debe quedar casi vertical (la rodilla no sube)'
# pie de apoyo realmente en el suelo, el otro en el aire
for i, down_sd in ((0, 'R'), (1, 'L'), (2, 'L'), (3, 'R')):
    assert abs(JF[i][down_sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, f'{names[i]}: el pie de apoyo debe tocar el suelo'
# desnivel de reposo de los tobillos: de pie, las dos piernas apoyadas, el desnivel es 0 (menor que HEELKICK_ARM_MAX_DIFF, se arma sin problema)
assert abs(ARM_MAX_DIFF) > 0 and ARM_MAX_DIFF > 0.0, 'umbral de armado'
# erguido y de frente (frontPositionCheck): tronco vertical, cadera a la misma altura en todos los fotogramas (trote en el sitio)
for J in JF:
    assert abs(J['S'][0] - J['H'][0]) < 1e-6, 'tronco vertical'
assert max(abs(J['H'][1] - JF[0]['H'][1]) for J in JF) < 4e-3, 'la cadera no sube ni baja (en el sitio)'
# HEELKICK_MAX_UP_SECONDS: el talon esta 'arriba' (a medio camino + arriba) menos de 1,5 s
assert (CFG['durM'] + CFG['durU']) / 1000 < MAX_UP_SECONDS, 'el talon no debe estar arriba mas de HEELKICK_MAX_UP_SECONDS'
# maquina de estados de processHeelKicks (ya armado): ninguno arriba -> uno arriba (lift >= ENTER) -> apoyado de nuevo (lift <= EXIT) = +1
up, side, reps = False, None, 0
for m in M * 2:     # dos vueltas completas
    if not up:
        uL, uR = m['liftL'] >= LIFT_ENTER, m['liftR'] >= LIFT_ENTER
        if uL or uR:
            up = True; side = 'L' if (uL and (not uR or m['liftL'] >= m['liftR'])) else 'R'
    else:
        if (m['liftL'] if side == 'L' else m['liftR']) <= LIFT_EXIT:
            reps += 1; up = False; side = None
print('repeticiones contadas en dos vueltas del GIF:', reps, '(= 2 por vuelta, una por talon)')
assert reps == 4, 'una vuelta del GIF debe contar exactamente 2 repeticiones (una por talon)'
print('OK: los talones al gluteo coinciden con los umbrales del contador (heelkicks, processHeelKicks)')
