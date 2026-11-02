"""Dominadas commando (commando pull-up), vista de PERFIL (de lado a la camara), mirando a la DERECHA como en la foto de referencia.
Como se hace de verdad (MasterClass, GORnation, Workout Dojo, Calisthenai: "una mano delante de la otra, como agarrando un
fusil", "hands directly next to each other", "keep your body perpendicular to the bar") y como en la foto de referencia de Alex:
  - TODO el cuerpo mira hacia donde estan la barra y las manos: cara, pecho, codos (que se doblan hacia delante y abajo) y puntas
    de los pies apuntan al mismo lado; el pelo/la espalda quedan detras,
  - las DOS MANOS JUNTAS en la barra (casi tocandose), una delante de la otra, algo por delante de la cara,
  - el cuerpo entero (torso + piernas) forma una linea inclinada hacia ATRAS: la cabeza y los hombros se echan atras y las
    caderas y las piernas quedan por delante; al subir se echa mas atras que colgado,
  - un HOMBRO llega a la barra y la cabeza pasa POR UN LADO de la barra (no por encima); en la siguiente repeticion, por el otro.
La app lo cuenta de perfil (workout.js: COMMANDO_*): barra horizontal en la imagen; la nariz llega a la altura de la barra
(COMMANDO_BAR_MARGIN_FACTOR) y el brazo que mas se dobla queda a <= COMMANDO_TOP_ELBOW_MAX_DEG = 110.
De perfil el lado por el que pasa la cabeza es PROFUNDIDAD: el GIF lo cuenta con 4 fotogramas (colgado -> arriba con la cabeza
por el lado cercano a la camara -> colgado -> arriba por el lado lejano), con la oclusion (en el 2º ascenso la barra cruza por
delante del cuello) y con un recuadro gris "visto desde arriba" (barra = linea, cabeza = circulo).
Al final se comprueban los umbrales del contador contra la geometria dibujada.
Uso: python ex_dominadas_commando.py [carpeta_salida] [clave=valor ...]   (genera dominadas-commando.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.3
CFG = dict(h_near=0.12, h_far=0.30, straight=0.99, sh_dy=0.12, margin=0.6, post=1.45, knee=14, mirror=0,
           lean=18, lean_a=8, head=97, leg_gap=9, foot=78, elb_dx=0.28, elb_dy=0.42, inset_x=2.8, inset_y=2.0, inset_s=1.0)
# h_near / h_far: distancia de cada mano al hombro, hacia DELANTE (las dos manos juntas, una delante de otra)
# straight: fraccion del brazo estirado colgado (1 = recto del todo); sh_dy: hombro por debajo de la barra arriba (el hombro "toca" la barra)
# lean / lean_a: grados que el cuerpo entero se echa hacia ATRAS (cabeza atras, piernas por delante), arriba / colgado abajo
# elb_dx / elb_dy: arriba, codo del brazo cercano respecto al hombro (hacia delante y abajo, ACORTADO por la perspectiva)
# head: direccion de la cabeza (90 = vertical; >90 = mirando algo hacia delante); leg_gap/foot: separacion entre piernas y flexion del pie
# mirror: 0 = mira a la derecha (como la foto), 1 = a la izquierda (espejo)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

COMMANDO_TOP_ELBOW_MAX_DEG = 110      # mismos umbrales que workout.js
COMMANDO_BAR_MARGIN_FACTOR = 0.60
COMMANDO_UNIT_PER_TORSO = 0.75
PULLUP_MIN_RISE_FACTOR = 0.40
REACH = L_UA + L_FA

# --- brazo 'pts': codo y muñeca dados a mano (brazo ACORTADO por la perspectiva: el codo sale hacia la camara / el fondo)
_limb_arm_orig = figura.limb_arm


def _limb_arm(spec, S, hd, bel):
    if spec[0] == 'pts':
        return S, np.array(spec[1], float), np.array(spec[2], float)
    return _limb_arm_orig(spec, S, hd, bel)


figura.limb_arm = _limb_arm

# --- pie 'libre': igual que figura.limb_leg, pero el talon se coloca del lado de la PLANTA (hacia abajo) tambien cuando el pie apunta
#     a la izquierda (figura.py asume pie a la derecha y al espejar el talon quedaba al reves: pies deformes). Misma idea que el
#     'flat' de ex_crunch.py. spec = ('fk', muslo, espinilla, direccion_del_pie, 'libre')
_limb_leg_orig = figura.limb_leg


def _limb_leg(spec, H):
    if len(spec) > 4 and spec[4] == 'libre':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        d = dv(spec[3]); p = rot(d, -90) if d[0] >= 0 else rot(d, 90)           # planta hacia abajo
        he = a + p * 0.10 - d * 0.07
        return H, k, a, he, he + d * 0.44
    return _limb_leg_orig(spec, H)


figura.limb_leg = _limb_leg

P = CFG['post']; hn, hf = CFG['h_near'], CFG['h_far']
RIG = [('bar', BAR, -P, P), ('post', -P, 0.0, BAR + 0.25), ('post', P, 0.0, BAR + 0.25)]
K = CFG['knee']
# En coordenadas de autoria el muñeco MIRA A LA DERECHA (adelante = +x, atras = -x); al final se espeja si mirror=1.
# Las manos quedan POR DELANTE del hombro (x positiva): la delantera (brazo cercano) en +h_near y la trasera (lejano) en +h_far.


def piernas(lean):
    """Piernas colgando como continuacion del tronco: todo el cuerpo esta echado 'lean' grados hacia ATRAS, asi que la cadera y
    las piernas quedan POR DELANTE (hacia donde mira), casi rectas, juntas pero una algo adelantada a la otra, y los pies con la
    punta hacia delante y un poco abajo (pie = espinilla + 78 grados, como una zapatilla colgando)."""
    t1 = 270 + lean; s1 = t1 - K * 0.5
    t2 = 270 + lean - CFG['leg_gap']; s2 = t2 - K
    return dict(near_leg=('fk', t1, s1, s1 + CFG['foot'], 'libre'), far_leg=('fk', t2, s2, s2 + CFG['foot'], 'libre'))


def colgado(sh_y):
    la = CFG['lean_a']
    return dict(f=1, ground=False, sh=(0, sh_y), torso=90 + la, head=90 + la * 0.5,
                near_arm=('ik', (hn, BAR), 'cw'), far_arm=('ik', (hf, BAR), 'cw'), **piernas(la))


def arriba(sh_y):
    """Un hombro llega a la barra (queda a 'sh_dy' por debajo), la cabeza asoma por encima a un lado de la barra, mirando a la
    barra, y el cuerpo se echa 'lean' grados hacia atras. De perfil los brazos se ven acortados: los codos salen hacia DELANTE y
    abajo (hacia donde mira) y los antebrazos suben hasta las manos, juntas en la barra delante de la cara."""
    S = np.array([0.0, sh_y]); dx, dy = CFG['elb_dx'], CFG['elb_dy']; ln = CFG['lean']
    return dict(f=1, ground=False, sh=(0, sh_y), torso=90 + ln, head=CFG['head'],
                near_arm=('pts', S + np.array([dx, -dy]), (hn, BAR)),
                far_arm=('pts', S + np.array([dx * 0.7, -dy * 0.85]), (hf, BAR)), **piernas(ln))


def espejo(p):
    """Mismo muñeco mirando al lado contrario (x -> -x, angulos a -> 180 - a)."""
    q = dict(p); q['f'] = -p['f']
    q['torso'] = 180 - p['torso']; q['head'] = 180 - p['head']; q['sh'] = (-p['sh'][0], p['sh'][1])
    for sd in ('near', 'far'):
        k = sd + '_arm'; a = p[k]
        if a[0] == 'ik':
            q[k] = ('ik', (-a[1][0], a[1][1]), 'ccw' if a[2] == 'cw' else 'cw')
        else:
            q[k] = ('pts', np.array([-a[1][0], a[1][1]]), (-a[2][0], a[2][1]))
        k = sd + '_leg'; a = p[k]
        q[k] = ('fk', 180 - a[1], 180 - a[2], 180 - a[3]) + tuple(a[4:])
    return q


dyA = np.sqrt((CFG['straight'] * REACH) ** 2 - hf ** 2)
A0 = colgado(BAR - dyA)
B0 = arriba(BAR - CFG['sh_dy'])
M = bool(CFG['mirror'])
A, B = (espejo(A0), espejo(B0)) if M else (A0, B0)
FRENTE = -1 if M else 1                                      # signo en pantalla de "adelante" (mirando a la derecha, +x)


def codo(J, sd):
    sh, e, w_ = J[sd + '_arm']; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


# --- comprobacion contra el contador (unidad commando = 0.75 * largo de tronco; el tronco mide 1 en la figura)
JA, JB = build_side(A), build_side(B)
unit = COMMANDO_UNIT_PER_TORSO * float(np.linalg.norm(JB['S'] - JB['H']))
for nombre, J in (('abajo', JA), ('arriba', JB)):
    for sd, hh in (('near', hn), ('far', hf)):
        w_ = J[sd + '_arm'][2]
        assert abs(w_[1] - BAR) < 0.03 and abs(w_[0] - FRENTE * hh) < 0.03, f'muñeca {sd} fuera de la barra o de su sitio ({nombre}): {w_}'
nariz_y = JB['hd'][1]                                                   # centro de la cabeza ~ altura de la nariz
sube = JB['S'][1] - JA['S'][1]
elb_min = min(codo(JB, 'near'), codo(JB, 'far'))
inc_a = np.degrees(np.arctan2(abs(JA['S'][0] - JA['H'][0]), JA['S'][1] - JA['H'][1]))
inc_b = np.degrees(np.arctan2(abs(JB['S'][0] - JB['H'][0]), JB['S'][1] - JB['H'][1]))
print(f'abajo: codos {codo(JA, "near"):.0f}° / {codo(JA, "far"):.0f}°, muñecas por encima de los hombros: '
      f'{JA["near_arm"][2][1] > JA["near_arm"][0][1] and JA["far_arm"][2][1] > JA["far_arm"][0][1]}; torso inclinado {inc_a:.0f}°')
print(f'arriba: codo que mas se dobla {elb_min:.0f}° (<= {COMMANDO_TOP_ELBOW_MAX_DEG}); '
      f'nariz {nariz_y - BAR:+.2f} sobre la barra (vale hasta -{COMMANDO_BAR_MARGIN_FACTOR * unit:.2f}); '
      f'subida {sube:.2f} (minimo {PULLUP_MIN_RISE_FACTOR * unit:.2f}); hombro a {BAR - JB["S"][1]:.2f} de la barra; torso inclinado {inc_b:.0f}°')
assert elb_min <= COMMANDO_TOP_ELBOW_MAX_DEG
assert nariz_y >= BAR - COMMANDO_BAR_MARGIN_FACTOR * unit
assert sube >= PULLUP_MIN_RISE_FACTOR * unit


def cara(J):
    """Nariz, ojo y oreja bien visibles para que se vea hacia donde mira (la cabeza de figura.py solo lleva un bultito)."""
    hd, face = J['hd'], J['face']
    v = (hd - J['S']) / (np.linalg.norm(hd - J['S']) + 1e-9); hc = hd + v * 0.035
    fa = np.arctan2(face[1], face[0]); d_ = lambda a: np.array([np.cos(a), np.sin(a)])
    up = np.array([-face[1], face[0]]); up = up if up[1] > 0 else -up
    base = [hc + 0.265 * d_(fa + dd) for dd in (-0.17, 0.0, 0.17)]
    tip = hc + 0.318 * d_(fa - 0.05)
    ojo = hc + 0.14 * d_(fa) + up * 0.07
    oreja = hc - 0.04 * d_(fa) - up * 0.02

    def f(pen):
        pen.paint([('p', np.array([base[0], tip, base[2]]))])                       # nariz
        pen.paint([('c', ojo, 0.022)])                                              # ojo
        pen.line(smooth_curve([oreja + up * 0.06, oreja - d_(fa) * 0.04, oreja - up * 0.06]), w=pen.c.LI * 0.9)   # oreja
    return f


def extras_de(pose_, cuerpo_detras_de_la_barra=False, con_cara=True):
    """Puños (los dos juntos, agarrando la barra: la barra pasa POR DELANTE del puño y los nudillos asoman por encima) y, si el
    cuerpo va por el lado LEJANO, antes de los puños se repinta la barra por delante del cuello/hombro."""
    J = build_side(pose_); ex = []
    if con_cara:                                  # colgado, el brazo tapa la cara: sin nariz ni ojo encima del brazo
        ex.append(cara(J))
    if cuerpo_detras_de_la_barra:
        sx = float(J['S'][0])
        ex.append(lambda pen, sx=sx: pen.line([(sx - 0.45, BAR), (sx + 0.45, BAR)], w=pen.c.LW * 1.3))

    def puño(pen, w_):
        c = pen.c
        pen.paint([('c', (w_[0], BAR + 0.012), 0.075)])
        pen.line([(w_[0] - 0.14, BAR), (w_[0] + 0.14, BAR)], w=c.LW * 1.3)
        for dx in (-0.035, 0.0, 0.035):
            pen.line([(w_[0] + dx, BAR + 0.015), (w_[0] + dx, BAR + 0.065)], w=c.LI * 0.8)

    for sd in ('far', 'near'):
        w_ = J[sd + '_arm'][2]
        ex.append(lambda pen, w_=w_: puño(pen, w_))
    return ex


def vista_cenital(lado):
    """Recuadro gris 'visto desde arriba': linea = barra, las dos manos JUNTAS en el centro, circulo = cabeza. lado: 0 = colgado
    (cabeza justo bajo la barra), -1 = por el lado CERCANO a la camara (abajo en el recuadro), +1 = por el LEJANO (arriba).
    El circulo punteado gris es el lado al que ira en la siguiente repeticion."""
    k_ = CFG['inset_s']
    cx, cy, hw, hh, off, r = CFG['inset_x'], CFG['inset_y'], 0.95 * k_, 0.70 * k_, 0.34 * k_, 0.20 * k_

    def f(pen):
        pen.line([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh), (cx - hw, cy - hh)],
                 w=pen.c.LI * 0.8, col=FLOOR)
        pen.line([(cx - hw + 0.12, cy), (cx + hw - 0.12, cy)], w=pen.c.LW * 0.9)                       # la barra
        if lado == 0:
            pen.paint([('c', (cx, cy), r)])
        else:
            pen.paint([('c', (cx, cy + lado * off), r)])
            th = np.linspace(0, 2 * np.pi, 48)                                                         # circulo punteado (otro lado)
            for a0 in range(0, 48, 6):
                seg = [(cx + r * np.cos(t), cy - lado * off + r * np.sin(t)) for t in th[a0:a0 + 3]]
                pen.line(seg, w=pen.c.LI * 0.8, col=GREY_ARROW)
        for sg in (1, -1):                                                                             # las dos manos juntas, una delante de otra
            pen.paint([('c', (cx + sg * 0.085 * k_, cy), 0.055 * k_)])
    return f


render_scene([A, B, A, B], OUT + 'dominadas-commando', props=RIG, durations=[1000, 1300, 1000, 1300], margin=CFG['margin'],
             extras=[extras_de(A, con_cara=False) + [vista_cenital(0)], extras_de(B) + [vista_cenital(-1)], extras_de(A, con_cara=False) + [vista_cenital(0)],
                     extras_de(B, cuerpo_detras_de_la_barra=True) + [vista_cenital(+1)]])
