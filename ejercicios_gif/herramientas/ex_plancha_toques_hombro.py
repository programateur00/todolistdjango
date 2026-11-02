"""Plancha con toques de hombro (plank shoulder taps), vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, estilo, suelo y flechas grises que flexiones / flexiones-con-palmada. SIN cara (ni nariz ni ojo ni oreja: no se usa cara(), cabeza lisa).
Como lo mira la app (workout.js: processPlankShoulderTaps, PLANKTAP_*, counter "plankshouldertaps", slug plank-shoulder-taps, migracion 0110): de PERFIL,
tumbado boca abajo en PLANCHA ALTA (manos bajo los hombros, cuerpo recto). El contador NO mira el codo: mira la ALTURA RELATIVA de las dos muñecas
(en largos de cuerpo = distancia hombro-tobillo) respecto a la referencia que aprende al armar (las dos manos apoyadas):
  - ARMAR: inclinacion hombro-cadera <= ON_GROUND_MAX_TILT_DEG = 40, hombro-cadera-tobillo >= PLANKTAP_ARM_LINE_MIN_DEG = 140,
    hombro por encima de la muñeca apoyada >= PLANKTAP_SHOULDER_CLEAR_FACTOR = 0.10 y manos a la misma altura (< PLANKTAP_LIFT_ENTER = 0.13),
  - MANO LEVANTADA: una muñeca sube >= PLANKTAP_LIFT_ENTER = 0.13 sobre la otra,
  - TOQUE: al volver a apoyar (diferencia <= PLANKTAP_LIFT_EXIT = 0.06) cuenta 1 toque; cada mano (derecha e izquierda) suma. Si la mano se queda en el
    aire mas de PLANKTAP_MAX_RAISE_MS = 4 s no cuenta; la serie se cierra si el tronco pasa de PUSHUP_BROKEN_TILT_DEG = 60° de inclinacion.
El cuerpo (hombros, cadera, pies) NO se mueve: solo sube una mano hacia el hombro contrario, lo toca y vuelve a apoyarse; despues la otra mano.
GIF de 8 fotogramas: plancha -> mano cercana subiendo (flecha gris arriba) -> TOQUE de hombro -> bajando (flecha gris abajo) -> plancha ->
mano lejana subiendo -> TOQUE -> bajando -> (vuelta a la plancha). La mano lejana va por detras del cuerpo, como en el resto de GIFs.
De perfil el cruce (cada mano va al hombro CONTRARIO) casi no se ve, asi que hay un recuadro gris "visto desde arriba" (como el de fondos): dos hombros,
las manos apoyadas bajo ellos y la mano que sube cruzando el cuerpo hasta el hombro de enfrente (flecha gris en la diagonal; circulo punteado = donde estaba apoyada).
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_plancha_toques_hombro.py [carpeta_salida] [clave=valor ...]   (genera plancha-con-toques-de-hombro.gif + PNG de cada fotograma;
     usar una carpeta temporal para la salida, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=172, hand_dx=0.0, far_dx=-0.07, foot=292, footF=296, far_t=1.5, headd=9, margin=0.32,
           tap_dx=-0.12, tap_dy=0.10, far_tap_dx=0.06, far_tap_dy=0.12, mid=0.5, mid_dx=0.0, behind=1, front=1,
           arrows=1, arrow_off=0.80, arrow_len=0.42, fingers=1, toe_x=0.0, inset=0, inset_x=1.15, inset_y=2.65, inset_s=1.2,
           durA=900, durU=450, durT=800, durD=450, durP=600)
# elbA: angulo del codo en la plancha alta (brazos casi rectos y verticales; el contador de toques no lo mira, es solo para que se vea bien)
# hand_dx: x de las manos respecto al hombro (0 = justo debajo del hombro); far_dx: la mano lejana queda algo detras
# foot / footF: angulo del pie cercano / lejano (apoyo en las puntas: ~290 = punta hacia abajo); far_t: grados que la pierna lejana se separa de la cercana
# headd: grados que la cabeza mira por encima de la linea del cuerpo (cuello neutro, mirada al suelo un poco por delante)
# tap_dx / tap_dy: donde queda la muñeca de la mano CERCANA en el toque, respecto al CENTRO DE LA CABEZA (x hacia delante, y hacia ABAJO): detras de la cabeza,
#   asi la mano desaparece tras ella y parece que llega al hombro de ENFRENTE (el contrario, que de perfil queda tapado)
# far_tap_dx / far_tap_dy: lo mismo para la mano LEJANA
# behind: 1 = la cabeza se repinta POR ENCIMA de la mano que cruza (el truco: la mano pasa por delante del pecho y se esconde detras de la cabeza); 0 = sin truco
# front: 1 = en el 2º toque (mano lejana) el antebrazo y la mano se repintan POR DELANTE de la cabeza (la mano aparece delante de ella); 0 = detras
# mid: fraccion del recorrido del fotograma intermedio (subiendo / bajando); mid_dx: desplazamiento extra en x de la muñeca intermedia
# inset / inset_x / inset_y / inset_s: recuadro gris "visto desde arriba" (como en fondos) que enseña el CRUCE (mano izquierda -> hombro derecho y al reves); inset=0 lo quita
# arrow_off / arrow_len: x de la flecha gris respecto a las manos apoyadas y su largo; arrows=0 las quita; fingers=0 quita las rayitas de los dedos
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
ON_GROUND_MAX_TILT_DEG = 40
PUSHUP_BROKEN_TILT_DEG = 60
PLANKTAP_ARM_LINE_MIN_DEG = 140
PLANKTAP_SHOULDER_CLEAR_FACTOR = 0.10
PLANKTAP_LIFT_ENTER = 0.13
PLANKTAP_LIFT_EXIT = 0.06

WY = 0.09                       # altura de la muñeca con la palma apoyada en el suelo
HAND = 0                        # dedos hacia delante (derecha), palma plana en el suelo


def elbow_len(deg):
    """distancia hombro-muñeca para un angulo de codo dado"""
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


def pose_t(t, hip):
    """pose del cuerpo recto (tabla) con el tronco a t grados sobre la horizontal; las manos se ponen despues"""
    f1 = dict(f=1, ground=False, hip=hip, torso=t, head=t + CFG['headd'])
    legs = dict(near_leg=('fk', 180 + t, 180 + t, CFG['foot']),
                far_leg=('fk', 180 + t + CFG['far_t'], 180 + t + CFG['far_t'], CFG['footF']))
    return dict(f1, **legs, near_arm=('fk', 270, 0), far_arm=('fk', 270, 0))


def feet_low(J):
    """punto mas bajo de las piernas (con el mismo margen que figura.ground_shift)"""
    lows = []
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        lows += [k[1] - 0.13, he[1] - 0.04, to[1] - 0.04, a[1] - 0.07]
    return min(lows)


def toe_x(J):
    return min(J[s + '_leg'][4][0] for s in ('near', 'far'))


# ---- plancha alta: el cuerpo recto como una tabla apoyado en las puntas de los pies (toe_x) y en las manos ----
_T = np.linspace(2, 50, 4801)
_S = []
for _t in _T:
    _J = build_side(pose_t(_t, (0.0, 0.0)))
    _dy = -feet_low(_J); _dx = CFG['toe_x'] - toe_x(_J)
    _S.append((_J['S'] + np.array([_dx, _dy]), (_dx, _dy)))

shA = WY + elbow_len(CFG['elbA'])              # hombro a la altura que da el brazo casi recto y VERTICAL (muñeca justo debajo del hombro)
iA = min(range(len(_T)), key=lambda i: abs(_S[i][0][1] - shA))
assert abs(_S[iA][0][1] - shA) < 2e-3, 'no hay solucion de postura en la plancha'
tA, hipA = float(_T[iA]), _S[iA][1]
SA = np.array(_S[iA][0])                       # hombro (FIJO en toda la animacion)
HX = SA[0] + CFG['hand_dx']                    # x de las manos apoyadas (FIJAS)
HXF = HX + CFG['far_dx']                       # mano lejana, un pelin detras

W_NEAR_GROUND = np.array([HX, WY])
W_FAR_GROUND = np.array([HXF, WY])
_Jh = build_side(pose_t(tA, hipA))
_v = (_Jh['hd'] - _Jh['S']) / np.linalg.norm(_Jh['hd'] - _Jh['S'])
HC = _Jh['hd'] + _v * 0.035                    # centro de la cabeza dibujada (figura.draw_side)
W_NEAR_TAP = HC + np.array([CFG['tap_dx'], -CFG['tap_dy']])
W_FAR_TAP = HC + np.array([CFG['far_tap_dx'], -CFG['far_tap_dy']])


def hand_to_shoulder(w):
    """direccion de la mano en el toque: de la muñeca hacia el centro de la cabeza (los dedos quedan dentro de la cabeza, ocultos)"""
    return ang(HC - np.asarray(w, float))


def arm_spec(w, a):
    return ('ik', tuple(w), 'cw'), a


def pose(near=None, far=None):
    """plancha alta con el cuerpo FIJO. near / far = None (mano apoyada) o fraccion 0..1 del recorrido hacia el hombro (1 = toque)"""
    p = pose_t(tA, hipA)
    for sd, f, g, tp in (('near', near, W_NEAR_GROUND, W_NEAR_TAP), ('far', far, W_FAR_GROUND, W_FAR_TAP)):
        if f is None:
            p[sd + '_arm'] = ('ik', tuple(g), 'cw'); p[sd + '_hand'] = HAND
        else:
            w = g + (tp - g) * f + np.array([CFG['mid_dx'] * 4 * f * (1 - f), 0.0])   # arco hacia delante a medio recorrido
            p[sd + '_arm'] = ('ik', tuple(w), 'cw')
            p[sd + '_hand'] = HAND + (hand_to_shoulder(w) - HAND) * min(1.0, 2.0 * f)   # a medio camino ya apunta hacia la cabeza
    return p


MID = CFG['mid']
P0 = pose()
N_UP, N_TAP = pose(near=MID), pose(near=1.0)
F_UP, F_TAP = pose(far=MID), pose(far=1.0)
frames = [P0, N_UP, N_TAP, N_UP, P0, F_UP, F_TAP, F_UP]
durs = [CFG['durA'], CFG['durU'], CFG['durT'], CFG['durD'], CFG['durP'], CFG['durU'], CFG['durT'], CFG['durD']]

JS = [build_side(p_) for p_ in frames]
J0 = JS[0]


def dedos(J, sd='near'):
    """rayitas de los dedos sobre la mano apoyada (la mano es un tubo corto; con ellas se lee la palma plana en el suelo)"""
    def f(pen):
        if not CFG['fingers']:
            return
        w_, tip = J[sd + '_arm'][2], J[sd + '_handtip']
        for k_ in (0.12, 0.20):
            x = tip[0] - k_
            pen.line([(x, w_[1] + 0.045), (x, w_[1] + 0.085)], w=pen.c.LI * 0.8)
    return f


AX = HX + CFG['arrow_off']
Y_LO, Y_HI = WY + 0.10, float(min(W_NEAR_TAP[1], W_FAR_TAP[1]))


def flecha(subiendo):
    def f(pen):
        if not CFG['arrows']:
            return
        m = (Y_LO + Y_HI) / 2; h = CFG['arrow_len'] / 2
        a, b = (m - h, m + h) if subiendo else (m + h, m - h)
        draw_line_arrow(pen, (AX, a), (AX, b))
    return f


def cenital(nf, ff, flecha_=0):
    """Recuadro gris 'visto desde arriba' (cabeza a la derecha, como en el perfil; abajo = lado cercano a la camara, arriba = lado lejano).
    nf / ff = None (mano apoyada) o fraccion 0..1 del recorrido de la mano cercana / lejana hacia el hombro CONTRARIO (1 = toque).
    flecha_ = +1 la mano sube cruzando / -1 vuelve a apoyarse / 0 sin flecha. Circulo punteado = donde esta apoyada la mano que se ha levantado."""
    k_ = CFG['inset_s']; cx, cy, hw, hh = CFG['inset_x'], CFG['inset_y'], 1.0 * k_, 0.78 * k_
    g = 0.46 * k_                               # medio ancho de hombros
    sx = cx + 0.22 * k_                         # x de la linea de hombros
    hx_ = sx + 0.20 * k_                        # las manos apoyadas quedan algo por delante (bajo el hombro no se distinguirian de el)

    def f(pen):
        if not CFG['inset']:
            return
        LI, LW = pen.c.LI, pen.c.LW
        pen.line([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh), (cx - hw, cy - hh)], w=LI * 0.8, col=FLOOR)
        pen.line([(sx, cy - g), (sx, cy + g)], w=LW * 0.9)                                    # hombros
        pen.line([(sx, cy), (cx - 0.78 * k_, cy)], w=LW * 0.9)                                # columna hasta los pies
        pen.line([(cx - 0.62 * k_, cy - 0.20 * k_), (cx - 0.62 * k_, cy + 0.20 * k_)], w=LW * 0.9)   # cadera
        pen.paint([('c', (sx + 0.30 * k_, cy), 0.14 * k_)])                                   # cabeza
        for sg, fr in ((-1, nf), (1, ff)):          # sg = -1 lado cercano (abajo), +1 lado lejano (arriba)
            home = np.array([hx_, cy + sg * g]); tgt = np.array([sx - 0.10 * k_, cy - sg * (g - 0.02 * k_)])
            if fr is None:
                pen.paint([('c', tuple(home), 0.065 * k_)])
                continue
            th = np.linspace(0, 2 * np.pi, 48)
            for a0 in range(0, 48, 6):
                pen.line([home + 0.075 * k_ * np.array([np.cos(t), np.sin(t)]) for t in th[a0:a0 + 3]], w=LI * 0.8, col=GREY_ARROW)
            pen.paint([('c', tuple(home + (tgt - home) * fr), 0.065 * k_)])                    # la mano que cruza
            if flecha_:
                v = tgt - home; n_ = np.array([-v[1], v[0]]) / np.linalg.norm(v)
                a_, b_ = home + v * 0.18 + n_ * 0.20 * k_, home + v * 0.86 + n_ * 0.20 * k_
                draw_line_arrow(pen, *( (a_, b_) if flecha_ > 0 else (b_, a_) ))
    return f


def cabeza_encima(J):
    """EL TRUCO: repinta la cabeza (mismo poligono que figura.draw_side) por encima de la mano que cruza, que asi se esconde detras de ella.
    No se repinta el cuello para no tapar el hombro."""
    def f(pen):
        if not CFG['behind']:
            return
        S, hd, face = J['S'], J['hd'], J['face']
        v = (hd - S) / (np.linalg.norm(hd - S) + 1e-9)
        ang_ax = np.arctan2(v[1], v[0]); ang_face = np.arctan2(face[1], face[0])
        th_ = np.linspace(0, 2 * np.pi, 120, endpoint=False)
        ra, rb_ = 0.30, 0.245
        rad = ra * rb_ / np.sqrt((rb_ * np.cos(th_)) ** 2 + (ra * np.sin(th_)) ** 2)
        dth = lambda a: np.angle(np.exp(1j * (th_ + ang_ax - a)))
        rad = rad + 0.040 * np.exp(-(dth(ang_face) / 0.20) ** 2)
        rad = rad + 0.030 * np.exp(-(dth(ang_face + np.sign(np.sin(ang_face - ang_ax) + 1e-9) * 0.55) / 0.30) ** 2)
        hc = hd + v * 0.035
        pen.paint([('p', hc + np.stack([rad * np.cos(th_ + ang_ax), rad * np.sin(th_ + ang_ax)], 1))])
    return f


def mano_delante(J, sd='far', frac=0.12):
    """La mano del lado LEJANO que cruza al hombro CERCANO va por detras del cuerpo: en el toque se repinta POR DELANTE de todo (pecho y cabeza) la mano y el
    ultimo trozo (frac) del antebrazo, asi la mano aparece delante de la cabeza y el resto del brazo sigue detras."""
    def f(pen):
        if not CFG['front']:
            return
        s_, e_, w_ = J[sd + '_arm']
        m_ = w_ + (e_ - w_) * frac
        pen.paint(tube(m_, w_, 0.09, 0.085, bulge=0.05, peak=0.5))
        if sd + '_handtip' in J:
            pen.paint(tube(w_, J[sd + '_handtip'], 0.085, 0.06, bulge=0.1, peak=0.4))
    return f


# rayitas de los dedos solo en las manos apoyadas (la cercana; la lejana va tapada por el cuerpo)
CE = lambda i: cabeza_encima(JS[i])
MD = lambda i: mano_delante(JS[i])
extras = [[dedos(JS[0]), cenital(None, None)],
          [flecha(True), cenital(MID, None, +1), CE(1)],
          [cenital(1.0, None), CE(2)],
          [flecha(False), cenital(MID, None, -1), CE(3)],
          [dedos(JS[4]), cenital(None, None)],
          [dedos(JS[5]), flecha(True), cenital(None, MID, +1)],
          [dedos(JS[6]), cenital(None, 1.0), MD(6)],
          [dedos(JS[7]), flecha(False), cenital(None, MID, -1)]]
# encuadre fijo para los 8 fotogramas (flecha incluida)
bb = (AX - 0.15, 0.0, AX + 0.15, J0['hd'][1] + 0.3)
if CFG['inset']:
    _k = CFG['inset_s']
    bb = (min(bb[0], CFG['inset_x'] - 1.05 * _k), bb[1], bb[2], max(bb[3], CFG['inset_y'] + 0.85 * _k))
imgs = render_scene(frames, OUT + 'plancha-con-toques-de-hombro', durations=durs, margin=CFG['margin'], bbox_extra=bb, extras=extras)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def ang3(a, b, c):
    u, v = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def tilt(J):
    d = J['H'] - J['S']
    return float(np.degrees(np.arctan2(abs(d[1]), abs(d[0]))))


def body_len(J):
    """bodyLen del contador: distancia hombro-tobillo"""
    return float(np.linalg.norm(J['S'] - J['near_leg'][2]))


def wy(J, sd):
    return float(J[sd + '_arm'][2][1])


def sd_(J):
    """sd del contador = (muñeca izq. - muñeca der.) / bodyLen con la y de imagen (hacia abajo); aqui y va hacia arriba, asi que se invierte el signo.
    >0: la muñeca LEJANA esta mas BAJA (la cercana, levantada); <0: al reves"""
    return (wy(J, 'near') - wy(J, 'far')) / body_len(J)


def clear(J):
    """shoulderClear del contador: (muñeca mas baja - hombro) en imagen = (hombro - muñeca mas baja) con y arriba, en largos de cuerpo"""
    return (J['S'][1] - min(wy(J, 'near'), wy(J, 'far'))) / body_len(J)


nombres = ['plancha', 'cercana subiendo', 'cercana TOQUE', 'cercana bajando', 'plancha', 'lejana subiendo', 'lejana TOQUE', 'lejana bajando']
base = sd_(J0)
for n_, J in zip(nombres, JS):
    print(f"{n_:17s}: linea hombro-cadera-tobillo {ang3(J['S'], J['H'], J['near_leg'][2]):.0f}° | inclinacion {tilt(J):.0f}° | "
          f"hombro sobre mano apoyada {clear(J):.2f} | diferencia entre manos {sd_(J) - base:+.2f} (sube >= {PLANKTAP_LIFT_ENTER}, cuenta al volver a <= {PLANKTAP_LIFT_EXIT}) | "
          f"muñeca cercana ({J['near_arm'][2][0]:.2f}, {J['near_arm'][2][1]:.2f}) lejana ({J['far_arm'][2][0]:.2f}, {J['far_arm'][2][1]:.2f})")
# --- armar: plancha, manos a la misma altura
for J in (JS[0], JS[4]):
    assert abs(sd_(J) - base) <= PLANKTAP_LIFT_EXIT and abs(sd_(J)) < PLANKTAP_LIFT_ENTER, 'plancha: las dos manos a la misma altura (diferencia <= 0.06)'
# --- el cuerpo es una tabla en todos los fotogramas
for J in JS:
    assert ang3(J['S'], J['H'], J['near_leg'][2]) >= PLANKTAP_ARM_LINE_MIN_DEG, 'el cuerpo debe quedar en linea recta (hombro-cadera-tobillo >= 140)'
    assert tilt(J) <= ON_GROUND_MAX_TILT_DEG, 'tumbado de verdad: inclinacion hombro-cadera <= 40'
    assert tilt(J) < PUSHUP_BROKEN_TILT_DEG
    assert clear(J) >= PLANKTAP_SHOULDER_CLEAR_FACTOR, 'el hombro debe quedar por encima de la muñeca apoyada (>= 0.10 largos de cuerpo)'
    assert abs(feet_low(J)) < 3e-3, 'los pies deben tocar el suelo'
    assert abs(J['near_leg'][4][0] - J0['near_leg'][4][0]) < 2e-3, 'los pies no se mueven'
    assert np.allclose(J['S'], J0['S'], atol=1e-6) and np.allclose(J['H'], J0['H'], atol=1e-6), 'el cuerpo (hombros y cadera) no se mueve'
# --- la mano apoyada no se mueve cuando la otra sube
for J in JS[1:4]:
    assert np.allclose(J['far_arm'][2], J0['far_arm'][2], atol=1e-6), 'mano lejana apoyada: no se mueve'
for J in JS[5:8]:
    assert np.allclose(J['near_arm'][2], J0['near_arm'][2], atol=1e-6), 'mano cercana apoyada: no se mueve'
# --- mano levantada: sube >= PLANKTAP_LIFT_ENTER sobre la otra; el signo cambia de mano (derecha e izquierda suman)
for J in (JS[1], JS[2], JS[3]):
    assert sd_(J) - base >= PLANKTAP_LIFT_ENTER, 'mano cercana levantada: >= 0.13 largos de cuerpo por encima de la otra'
for J in (JS[5], JS[6], JS[7]):
    assert sd_(J) - base <= -PLANKTAP_LIFT_ENTER, 'mano lejana levantada: >= 0.13 largos de cuerpo por encima de la otra'
# --- toque: la muñeca y los dedos quedan sobre la cabeza (la cercana tapada POR ella, la lejana POR DELANTE de ella): la mano llega al hombro de enfrente
for J, sd in ((JS[2], 'near'), (JS[6], 'far')):
    hc_ = J['hd'] + (J['hd'] - J['S']) / np.linalg.norm(J['hd'] - J['S']) * 0.035
    dw, dt = float(np.linalg.norm(J[sd + '_arm'][2] - hc_)), float(np.linalg.norm(J[sd + '_handtip'] - hc_))
    print(f"toque {sd}: muñeca a {dw:.2f} y dedos a {dt:.2f} del centro de la cabeza (radio ~0.25)")
    assert dw < 0.22 and dt < 0.22, 'toque: la mano queda sobre la cabeza (cercana: detras de ella; lejana: delante)'
print('OK: plancha, mano cercana (derecha o izquierda) y mano lejana coinciden con los umbrales del contador (plankshouldertaps)')
