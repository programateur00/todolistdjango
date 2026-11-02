"""Elevación de talones (heel raise / calf raise), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que sentadillas / split squat / plank. SIN cara: ni nariz, ni ojo, ni oreja (no se usa cara() y la cabeza va LISA con plain_head=True,
sin el bultito de nariz/barbilla que lleva por defecto draw_side).
Como lo mira la app (workout.js: processHeelRaise, HEELRAISE_*, counter "heelraise", slug heel-raise, migracion 0112): de pie, de frente o de perfil (no exige ninguna). Mide SOLO lo que
sube cada talon respecto a la punta de su pie (la punta se queda en el suelo):
    lift = media( punta.y - talon.y , punta.y - tobillo.y )     (por pie, en anchos de imagen con el aspecto corregido)
    rel  = (lift - base) / largo de pierna (cadera->tobillo),     base = lift con los talones apoyados al armar
  - ARMAR: de pie, quieto, talones apoyados, los dos pies enteros a la vista,
  - ARRIBA: rel media >= HEELRAISE_UP = 0.045 Y cada pie >= HEELRAISE_UP_EACH = 0.030 (un solo talon = andar, no vale),
  - ABAJO (cuenta 1 repeticion): rel media <= HEELRAISE_DOWN = 0.022.
Forma correcta (Planfit, Bodybuilding.com, NHS "calf raises"): de pie, pies a la anchura de las caderas apuntando al frente, tronco ERGUIDO, manos en las caderas (o en la pared para
equilibrarse); se SUBE sobre las puntas de los pies (la zapatilla se DOBLA por la base de los dedos: dedos y planta delantera siguen planos en el suelo, solo se levanta el talon) todo lo alto
posible con las rodillas ESTIRADAS (no se doblan) y el cuerpo sube recto, sin inclinarse; arriba se aprieta un instante; se baja despacio hasta apoyar los talones.
Las puntas de los pies NO se mueven (el tobillo avanza un poco al rodar sobre la planta delantera, la cadera siempre queda justo encima del tobillo).
GIF de 4 fotogramas: talones apoyados (flecha gris arriba) -> subiendo -> arriba, sobre las puntas -> bajando (flecha gris abajo) -> (vuelta a los talones apoyados).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert), con las medidas en coordenadas de imagen normalizadas (la app corrige el aspecto con
videoHeight/videoWidth) y se simula la maquina de estados de processHeelRaise: tiene que contar exactamente 1 repeticion por vuelta.
Uso: python ex_elevacion_talones.py [carpeta_salida] [clave=valor ...]   (genera heel-raise.gif + PNG de cada fotograma; usar una carpeta temporal para probar)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(footM=28, footB=56,        # grados que se levanta el talon (giro del pie por detras de la base de los dedos; 0 = pie plano) a medio camino / arriba
           torso=90, head=90,         # tronco erguido y cuello neutro, mirada al frente
           far_dx=-0.07,              # el pie/pierna lejanos quedan algo por detras del cercano para que se vean los dos
           hand_dx=0.06, hand_dy=-0.88, farh_dx=-0.05, farh_dy=0.03, hand=-25,   # manos en las caderas (muñeca respecto al hombro) y direccion de los dedos
           margin=0.34, arrows=1, arrow_gap=0.85, arrow_len=0.5,
           durA=1200, durB=600, durC=1300, durD=600)
# footM / footB: 56° = talon ~0.26 largos de torso por encima del suelo (~13 cm en una persona real: una elevacion completa)
# hand_*: la muñeca va pegada a la cadera, el codo hacia atras (manos en las caderas); farh_*: el brazo lejano un pelin distinto para que se vean los dos
# arrow_gap / arrow_len: separacion de la flecha gris respecto a la espalda (por detras del muñeco, a la altura de los hombros) y su largo; arrows=0 las quita
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (processHeelRaise)
HEELRAISE_UP = 0.045
HEELRAISE_UP_EACH = 0.030
HEELRAISE_DOWN = 0.022
HEELRAISE_ARM_MAX_LEG_DIFF = 0.20
LEG = L_THIGH + L_SHIN                  # pierna ESTIRADA: cadera -> tobillo
FOOT = 0.44                             # largo del pie de figura.py (talon -> punta)
FORE = 0.30 * FOOT                      # punta -> base de los dedos (bisagra de la zapatilla); esa parte queda plana en el suelo
REAR = FOOT - FORE                      # talon -> base de los dedos: es lo que gira al levantar el talon
BALL_Y = 0.04                           # altura de la planta delantera sobre el suelo (igual que el pie plano de los demas GIFs: punta a 0.04)


# ---------------------------------------------------------------- pie DOBLADO por la base de los dedos (figura.limb_leg / figura.foot_poly solo saben hacer un pie rigido)
def rear_dirs(th):
    """direccion talon->base de los dedos y 'arriba' del pie trasero cuando el talon sube th grados"""
    return dv(-th), dv(90 - th)


def limb_leg_bent(spec, H):
    """spec = (kind, a, b, foot_angle, 'bent'): igual que figura.limb_leg pero con el pie doblado. foot_angle = -th (th = grados que sube el talon).
    Devuelve (cadera, rodilla, tobillo, talon_virtual, punta): la PUNTA es la real (plana en el suelo); el talon que se devuelve es el talon de un pie PLANO (a 'FOOT' a la izquierda de la punta)
    para que figura.draw_side dibuje las rayitas de los dedos como siempre; el talon real se calcula con real_heel()."""
    if len(spec) > 4 and spec[4] == 'bent':
        if spec[0] == 'fk':
            k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        else:
            k, a = ik2(H, spec[1], L_THIGH, L_SHIN, spec[2])
        dr, up = rear_dirs(-spec[3])
        he = a - up * 0.10 - dr * 0.07
        ball = he + dr * REAR
        to = ball + np.array([FORE, 0.0])
        return H, k, a, to - np.array([FOOT, 0.0]), to
    return _orig_limb(spec, H)


def foot_poly_bent(an, he_v, to, consistent=False):
    """zapatilla doblada: planta delantera plana (base de los dedos -> punta) + parte trasera girada th grados (talon -> base de los dedos). Con th = 0 es el pie plano de siempre."""
    ball = to - np.array([FORE, 0.0])
    th = np.degrees(np.arctan2(0.10, -(REAR - 0.07))) - ang(an - ball)       # giro de la parte trasera, deducido del tobillo
    dr, up = rear_dirs(th)
    he = ball - dr * REAR
    fu = np.array([0.0, 1.0])
    P0 = he - dr * 0.035                                                    # talon, abajo y atras
    P1 = to + np.array([0.04, 0.0])                                         # punta, abajo
    P2 = to + np.array([0.03, 0.045])                                       # punta, arriba
    P3 = ball + np.array([FORE * 0.33, 0.072])                              # empeine delantero (como el P3 de figura.foot_poly)
    bis = (fu + up) / np.linalg.norm(fu + up)
    H_ = ball + bis * (0.082 / max(np.cos(np.radians(th) / 2), 0.5))        # pliegue del empeine sobre la base de los dedos
    P4 = he + dr * 0.5 * FOOT + up * 0.105                                  # empeine medio
    P5 = an + dr * 0.05                                                     # delante del tobillo
    P6 = an - dr * 0.075 + up * 0.02                                        # detras del tobillo
    P7 = he - dr * 0.035 + up * 0.075                                       # talon, arriba
    return np.array([P0, ball, P1, P2, P3, H_, P4, P5, P6, P7])


_orig_limb = figura.limb_leg
figura.limb_leg = limb_leg_bent
figura.foot_poly = foot_poly_bent


def real_heel(J, sd):
    """talon real (centro del talon, como el que usa MediaPipe) del pie doblado dibujado en J"""
    an, to = J[sd + '_leg'][2], J[sd + '_leg'][4]
    ball = to - np.array([FORE, 0.0])
    th = np.degrees(np.arctan2(0.10, -(REAR - 0.07))) - ang(an - ball)
    dr, up = rear_dirs(th)
    return ball - dr * REAR, th


def ankle_for_ball(ball, th):
    """tobillo cuando la base de los dedos esta en 'ball' y el talon sube th grados"""
    dr, up = rear_dirs(th)
    return ball - dr * REAR + up * 0.10 + dr * 0.07


def pose(th):
    """pierna estirada con los talones levantados th grados; la cadera queda justo encima del tobillo (cuerpo recto) y la punta de los pies no se mueve"""
    ball_n = np.array([-FORE, BALL_Y])
    ball_f = np.array([CFG['far_dx'] - FORE, BALL_Y])
    an_n, an_f = ankle_for_ball(ball_n, th), ankle_for_ball(ball_f, th)
    hip = an_n + np.array([0.0, LEG])
    return dict(f=1, ground=False, plain_head=True, hip=tuple(hip), torso=CFG['torso'], head=CFG['head'],
                near_leg=('fk', 270, 270, -th, 'bent'),
                far_leg=('ik', tuple(an_f), 'ccw', -th, 'bent'),
                near_arm=('ikr', (CFG['hand_dx'], CFG['hand_dy']), 'cw'),               # manos en las caderas, codos hacia atras
                far_arm=('ikr', (CFG['hand_dx'] + CFG['farh_dx'], CFG['hand_dy'] + CFG['farh_dy']), 'cw'),
                near_hand=CFG['hand'], far_hand=CFG['hand'])


A, M, B = pose(0), pose(CFG['footM']), pose(CFG['footB'])
frames = [A, M, B, M]
durs = [CFG['durA'], CFG['durB'], CFG['durC'], CFG['durD']]
JSs = [build_side(p_) for p_ in frames]     # ground=False: ya estan con el suelo en y = 0 (planta delantera a BALL_Y)

# flecha gris POR DETRAS de la espalda a la altura de los hombros (los codos van hacia atras); alto = rango del hombro entre talones apoyados y arriba
AX = min(all_points(J)[:, 0].min() for J in JSs) - CFG['arrow_gap'] + 0.6
Y_LO, Y_HI = JSs[0]['S'][1], JSs[2]['S'][1]


def flecha(subiendo):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (Y_LO + Y_HI) / 2; h = CFG['arrow_len'] / 2
        a, b = (m - h, m + h) if subiendo else (m + h, m - h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


extras = [[flecha(True)], [], [], [flecha(False)]]
bb = (AX - 0.15, 0.0, AX + 0.15, JSs[2]['hd'][1] + 0.3)
imgs = render_scene(frames, OUT + 'heel-raise', durations=durs, margin=CFG['margin'], bbox_extra=bb, extras=extras, ground_all=False)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processHeelRaise)
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


allp = np.vstack([all_points(J) for J in JSs])
xc = (allp[:, 0].min() + allp[:, 0].max()) / 2
Wf = (allp[:, 0].max() - allp[:, 0].min()) / 0.85


def make_img(aspect):
    """aspect = ancho/alto del video. Devuelve coordenadas normalizadas (x derecha, y ABAJO, como MediaPipe)"""
    Hf = Wf / aspect

    def img(p):
        return np.array([(p[0] - xc) / Wf + 0.5, 0.90 - p[1] / Hf])
    return img


def medidas(J, img, aspect):
    """lo mismo que processHeelRaise: lift y largo de pierna de cada pie, en anchos de imagen (aspecto corregido: aspecto de la app = alto/ancho)"""
    asp = 1.0 / aspect
    out = []
    for sd in ('near', 'far'):
        hp, kn, an, _, to = J[sd + '_leg']
        he = real_heel(J, sd)[0]
        hp, kn, an, he, to = [img(q) for q in (hp, kn, an, he, to)]
        lift = (((to[1] - he[1]) + (to[1] - an[1])) / 2) * asp
        leg = float(np.hypot(hp[0] - an[0], (hp[1] - an[1]) * asp))
        out.append(dict(lift=float(lift), leg=leg, knee=ang3(hp, kn, an)))
    return out


def rels(ms, ref):
    refleg = (ref[0]['leg'] + ref[1]['leg']) / 2
    return [(m['lift'] - r['lift']) / refleg for m, r in zip(ms, ref)]


nombres = ['talones apoyados', 'subiendo', 'arriba', 'bajando']
for asp in (16 / 9, 9 / 16, 1.0, 4 / 3, 3 / 4):
    img = make_img(asp)
    Ms = [medidas(J, img, asp) for J in JSs]
    ref = Ms[0]
    R = [rels(m, ref) for m in Ms]
    mean = [float(np.mean(r)) for r in R]; mn = [min(r) for r in R]
    if abs(asp - 16 / 9) < 1e-9:
        for i_, (n_, m_, mi, J) in enumerate(zip(nombres, mean, mn, JSs)):
            hr, th = real_heel(J, 'near')
            print(f"{n_:17s}: subida media {m_:+.3f} | cada pie >= {mi:+.3f} | rodilla {Ms[i_][0]['knee']:5.1f}° | talon {th:4.1f}° y {hr[1] - BALL_Y:+.2f} torsos sobre la punta")
    assert abs(mean[0]) < 1e-6, 'armar: con los talones apoyados la subida es 0 (la base)'
    assert mean[2] >= HEELRAISE_UP * 1.8 and mn[2] >= HEELRAISE_UP_EACH * 1.8, f'arriba: media >= {HEELRAISE_UP} y cada pie >= {HEELRAISE_UP_EACH}, con margen (aspecto {asp:.2f}: {mean[2]:.3f}/{mn[2]:.3f})'
    assert mean[1] > HEELRAISE_DOWN, 'a medio camino (bajando) todavia no cuenta la repeticion'
    assert abs(R[2][0] - R[2][1]) < 0.01, 'los dos pies suben igual'
    # --- maquina de estados de processHeelRaise (arma en 'down'; 3 vueltas): 1 repeticion por vuelta
    state, reps = 'down', 0
    for vuelta in range(3):
        for m_, mi in zip(mean + [mean[0]], mn + [mn[0]]):
            if state == 'down':
                if m_ >= HEELRAISE_UP and mi >= HEELRAISE_UP_EACH:
                    state = 'up'
            elif m_ <= HEELRAISE_DOWN:
                reps += 1; state = 'down'
    assert reps == 3, f'el contador debe sumar 1 repeticion por vuelta (aspecto {asp:.2f}: {reps} en 3 vueltas)'
    # armar: las dos piernas miden parecido y estan quietas
    assert abs(ref[0]['leg'] - ref[1]['leg']) <= HEELRAISE_ARM_MAX_LEG_DIFF * max(ref[0]['leg'], ref[1]['leg']), 'armar: piernas parejas'

# --- forma: rodillas estiradas, tronco recto, punta del pie fija y en el suelo, el talon sube y nada se hunde en el suelo
J0 = JSs[0]
for J in JSs:
    for sd in ('near', 'far'):
        hp, kn, an, _, to = J[sd + '_leg']
        he = real_heel(J, sd)[0]
        assert ang3(hp, kn, an) >= 175, 'rodillas estiradas arriba y abajo'
        assert abs(to[0] - J0[sd + '_leg'][4][0]) < 1e-9, 'la punta del pie no se mueve'
        assert abs(to[1] - BALL_Y) < 3e-3, 'la planta delantera sigue en el suelo'
        assert he[1] >= BALL_Y - 3e-3, 'el talon nunca baja del suelo (no lo atraviesa)'
    assert abs(J['H'][0] - J['near_leg'][2][0]) < 1e-9, 'la cadera queda justo encima del tobillo (cuerpo recto)'
    assert abs(J['S'][0] - J['H'][0]) < 1e-9, 'tronco erguido'
    assert J['plain_head'], 'cabeza lisa: sin nariz ni ojos'
assert JSs[2]['H'][1] - JSs[0]['H'][1] > 0.12, 'arriba el cuerpo sube de verdad'
print(f"OK: heel-raise coincide con los umbrales del contador (heelraise): arriba sube {np.mean(R[2]):.3f} de la pierna (>= {HEELRAISE_UP}, cada pie >= {HEELRAISE_UP_EACH}), "
      f"abajo 0 (<= {HEELRAISE_DOWN}); 1 repeticion por ciclo (aspectos 16:9, 9:16, 1:1, 4:3 y 3:4)")
