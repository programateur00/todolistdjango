"""Tuck Lever Bar (tuck front lever en barra), DE FRENTE y DE PERFIL en el MISMO GIF (dos paneles: izquierda = de frente, derecha = de perfil).
Mismo montaje (barra + postes), muñeco, manos agarradas y estilo que ex_dominadas.py / ex_dead_hang.py / ex_toes_to_bar.py / ex_dominadas_commando.py.
Como se hace de verdad (Calisthenai, Fitness Volt, Liftosaur: "brazos TOTALMENTE estirados, hombros bajados, espalda paralela al suelo, rodillas
al pecho, caderas a la altura de los hombros, la barra 'empujada' hacia las caderas"):
  - se parte de colgado (brazos estirados),
  - el cuerpo ENTERO gira alrededor de los hombros (los brazos no se doblan): las caderas suben hasta la altura de los hombros, la espalda queda
    HORIZONTAL mirando al suelo (el pecho al techo) y las rodillas suben hacia el pecho, con los talones cerca del culo,
  - se AGUANTA (es isometrico: mode=timed, counter_key=tucklever; reloj gris en el fotograma del aguante).
La app lo cuenta DE FRENTE (workout.js: checkTuckLeverPosture, TUCKLEVER_*): munecas por encima de los hombros (HANG_MARGIN_FACTOR = 0.08 anchos de
hombro) y rodilla (o tobillo, el que mejor se vea) como mucho TUCKLEVER_KNEE_MAX_GAP_FACTOR = 0.15 anchos de hombro POR DEBAJO del hombro (al armar;
0.4 ya aguantando): o sea, las piernas dobladas tienen que subir por encima del hombro, cerca de la barra. No mira la cadera ni la espalda: de perfil
tambien se ve la espalda horizontal, y eso es lo que esta en el panel derecho.
Los dos paneles salen del MISMO esqueleto 3D (lateral, y, z=hacia donde mira): el de perfil usa (z, y), el de frente (lateral, y - elev*z), asi que
alturas y proporciones coinciden. Al final se comprueban los umbrales del contador contra la geometria DIBUJADA en el panel frontal (assert).
Uso: python ex_tuck_lever.py [carpeta_salida] [clave=valor ...]   (genera tuck-lever-bar.gif; png=1 para guardar tambien los fotogramas)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figura
from figura import *
from PIL import ImageFont, ImageDraw

OUT = (sys.argv[1] if len(sys.argv) > 1 and '=' not in sys.argv[1] else '.').rstrip('/\\') + '/'
BAR = float(dict(a.split("=") for a in sys.argv[1:] if "=" in a).get("BAR", 4.0))
CFG = dict(grip=0.58, sw=0.34, reach=0.998, zbar=0.25, elev=0.22, hipw=0.15,
           phiB=48, kneeW=0.30, ankW=0.10,
           thA=272, shA=205, ftA=330,          # colgado: muslos casi verticales, rodillas dobladas hacia atras (los pies no tocan el suelo)
           thB=25, shB=285, ftB=335,           # a medio camino: rodillas delante y arriba, espinillas colgando
           thC=118, shC=330, ftC=335,          # tuck lever: muslo hacia la cabeza (angulo de cadera 50 grados), talones cerca del culo
           gap=5,                              # grados que se adelanta/atrasa la pierna lejana respecto a la cercana (profundidad en el perfil)
           pw=240, margin=0.22, labels=1, arrows=1, guide=1, clock=1, png=0, hold=1800)
# grip: mitad de la separacion de las manos (0.58 = un poco mas ancha que los hombros, como dead hang); sw: mitad del ancho de hombros
# reach: fraccion del brazo estirado (1 = recto del todo); zbar: la barra queda un poco por DELANTE de los hombros (empujar la barra hacia las caderas)
# elev: inclinacion de la vista frontal (la camara mira algo desde arriba: lo que esta mas cerca se ve algo mas abajo); phiB: giro del cuerpo a medio camino
# kneeW / ankW: separacion lateral de las rodillas / tobillos al subir; th*/sh*/ft*: muslo / espinilla / pie en grados (0 = hacia delante, 90 = arriba, vistos de perfil)
for a in sys.argv[1:]:
    if '=' in a:
        k, v = a.split('='); CFG[k] = float(v)

# --- mismos umbrales que workout.js
HANG_MARGIN_FACTOR = 0.08
TUCKLEVER_KNEE_MAX_GAP_FACTOR = 0.15
TUCKLEVER_KNEE_LOOSE_MAX_GAP_FACTOR = 0.4
REACH = L_UA + L_FA
g, SW_HALF, ZB, K = CFG['grip'], CFG['sw'], CFG['zbar'], CFG['elev']
SW = 2 * SW_HALF                                   # ancho de hombros dibujado
SY = BAR - float(np.sqrt((CFG['reach'] * REACH) ** 2 - (g - SW_HALF) ** 2 - ZB ** 2))      # altura de los hombros (fija: el cuerpo gira alrededor de ellos)
BAR_F = BAR - K * ZB                               # altura de la barra en la vista frontal (esta un poco por delante de los hombros)

# --- patas/brazos 'pts' (codo/rodilla dados a mano desde el esqueleto 3D) para build_side
_limb_arm_orig, _limb_leg_orig = figura.limb_arm, figura.limb_leg


def _limb_arm(spec, S, hd, bel):
    if spec[0] == 'pts':
        return S, np.array(spec[1], float), np.array(spec[2], float)
    return _limb_arm_orig(spec, S, hd, bel)


def _limb_leg(spec, H):
    if spec[0] == 'pts':
        k, a = np.array(spec[1], float), np.array(spec[2], float)
        d = dv(spec[3]); p = rot(d, -90)
        he = a + p * 0.10 - d * 0.07
        return H, k, a, he, he + d * 0.44
    return _limb_leg_orig(spec, H)


figura.limb_arm, figura.limb_leg = _limb_arm, _limb_leg


# ---------------------------------------------------------------- esqueleto 3D: (lateral, y, z)   z = hacia donde mira el muñeco (delante)
def seg3(L, dlat, ang):
    """vector de longitud L con 'dlat' de desplazamiento lateral; el resto va en el plano (z, y) con angulo 'ang' (0 = delante, 90 = arriba)"""
    m = float(np.sqrt(max(L * L - dlat * dlat, 1e-6)))
    return np.array([dlat, m * np.sin(np.deg2rad(ang)), m * np.cos(np.deg2rad(ang))])


def skeleton(phi, th, sh, ft, kneeW, ankW):
    """El cuerpo gira 'phi' grados alrededor de los hombros (0 = colgado, 90 = espalda horizontal, pecho al techo)."""
    S = np.array([0.0, SY, 0.0]); p = np.deg2rad(phi)
    H = S + np.array([0.0, -np.cos(p), np.sin(p)])                  # el torso mide 1
    hd = S + 0.52 * np.array([0.0, np.sin(np.deg2rad(90 + phi)), np.cos(np.deg2rad(90 + phi))])   # la cabeza sigue la linea del torso (cuello neutro)
    Jd = dict(phi=phi, S=S, H=H, hd=hd)
    for sd, sg in (('R', 1), ('L', -1)):
        far = (sd == 'L')
        gp = -CFG['gap'] if far else 0.0
        sho = S + np.array([sg * SW_HALF, 0, 0]); w = np.array([sg * g, BAR, ZB])
        v = w - sho; v = v * min(1.0, CFG['reach'] * REACH / np.linalg.norm(v))
        w = sho + v; e = sho + v * (L_UA / REACH)
        hp = H + np.array([sg * CFG['hipw'], 0, 0])
        k = hp + seg3(L_THIGH, sg * (kneeW - CFG['hipw']), th + gp)
        a = k + seg3(L_SHIN, sg * (ankW - kneeW), sh + gp)
        Jd[sd] = dict(sho=sho, e=e, w=w, hp=hp, k=k, a=a, ft=ft + gp)
    return Jd


A3 = skeleton(0, CFG['thA'], CFG['shA'], CFG['ftA'], CFG['hipw'], CFG['hipw'] * 0.8)
B3 = skeleton(CFG['phiB'], CFG['thB'], CFG['shB'], CFG['ftB'], 0.19, 0.12)
C3 = skeleton(90, CFG['thC'], CFG['shC'], CFG['ftC'], CFG['kneeW'], CFG['ankW'])
STATES = [A3, B3, C3, B3]


def zy(P):                      # perfil: x = z (delante = derecha), y
    return np.array([P[2], P[1]])


def fr(P):                      # frente: x = lateral, y - elev * z (lo mas cercano baja un poco)
    return np.array([P[0], P[1] - K * P[2]])


# ---------------------------------------------------------------- lienzo por paneles (misma escala en los dos)
class PCanvas(Canvas):
    def __init__(self, cx, cy, scale, pw):
        self.cx, self.cy, self.scale, self.pw = cx, cy, scale, pw
        self.LW = max(0.052 * scale, 3.0 * SS); self.LI = max(0.026 * scale, 1.6 * SS); self.floor_y = None

    def C(self, p):
        p = np.asarray(p, float)
        return np.stack([(p[..., 0] - self.cx) * self.scale + self.pw * SS / 2, -(p[..., 1] - self.cy) * self.scale + CH * SS / 2], -1)


# ================================================================= PANEL DE PERFIL
def pose_side(J3):
    ph = J3['phi']
    t = 90 + ph
    return dict(f=1, ground=False, sh=tuple(zy(J3['S'])), torso=t, head=t,
                near_arm=('pts', zy(J3['R']['e']), zy(J3['R']['w'])), far_arm=('pts', zy(J3['L']['e']), zy(J3['L']['w'])),
                near_leg=('pts', zy(J3['R']['k']), zy(J3['R']['a']), J3['R']['ft']), far_leg=('pts', zy(J3['L']['k']), zy(J3['L']['a']), J3['L']['ft']))


def cara(J):
    """Nariz, ojo y oreja (como en ex_dominadas_commando.py) para que se vea hacia donde mira."""
    hd, face = J['hd'], J['face']
    v = (hd - J['S']) / (np.linalg.norm(hd - J['S']) + 1e-9); hc = hd + v * 0.035
    fa = np.arctan2(face[1], face[0]); d_ = lambda a: np.array([np.cos(a), np.sin(a)])
    up = v                                                            # hacia la coronilla (el ojo va por encima de la nariz, tumbado o no)
    base = [hc + 0.265 * d_(fa + dd) for dd in (-0.17, 0.0, 0.17)]
    tip = hc + 0.318 * d_(fa - 0.05)
    ojo = hc + 0.14 * d_(fa) + up * 0.07
    oreja = hc - 0.04 * d_(fa) - up * 0.02

    def f(pen):
        pen.paint([('p', np.array([base[0], tip, base[2]]))])
        pen.paint([('c', ojo, 0.022)])
        if abs(face[0]) > 0.8:                                        # la oreja solo se ve bien con la cara de lado (tumbado parecia una sonrisa)
            pen.line(smooth_curve([oreja + up * 0.06, oreja - d_(fa) * 0.04, oreja - up * 0.06]), w=pen.c.LI * 0.9)
    return f


def barra_perfil(pen):
    """La barra vista DE PERFIL (por el extremo): un circulo."""
    pen.circ_px((ZB, BAR), pen.c.LW * 0.8, INK)


def punos_perfil(J):
    ex = []
    for sd in ('far', 'near'):
        w_ = J[sd + '_arm'][2]
        ex.append(lambda pen, w_=w_: (pen.paint([('c', (w_[0], BAR + 0.01), 0.085)]), barra_perfil(pen)))
    return ex


def guia_perfil(y):
    def f(pen):
        dashed(pen, (-1.05, y), (1.85, y))
    return f


def dashed(pen, a, b, n=18):
    a, b = np.asarray(a, float), np.asarray(b, float)
    for i in range(n):
        s0, s1 = i / n, (i + 0.55) / n
        pen.line([a + (b - a) * s0, a + (b - a) * s1], w=pen.c.LI * 0.9, col=GREY_ARROW)


# ================================================================= PANEL FRONTAL
def pose_front(J3):
    """Esqueleto 3D proyectado a la vista frontal (lo que ve la camara del movil)."""
    S, H = fr(J3['S']), fr(J3['H'])
    d = dict(H=H, S=S, n=np.array([1.0, 0.0]), ud=np.array([0.0, 1.0]), hd=fr(J3['hd']), hdir=90, back=False, t=90)
    for sd in 'RL':
        j = J3[sd]
        d[sd + '_arm'] = (fr(j['sho']), fr(j['e']), fr(j['w']))
        sg = 1 if sd == 'R' else -1
        d[sd + '_leg'] = (fr(j['hp']), fr(j['k']), fr(j['a']), sg)
    return d


def draw_front_lever(pen, J, shoe_dy=-0.085):
    """Como figura.draw_front pero para el cuerpo girado: torso ESCORZADO (mide menos que 1 en la imagen) y las piernas, que vienen hacia la camara,
    se pintan DESPUES del tronco, la cabeza y los brazos (lo que esta mas cerca tapa a lo de atras)."""
    c = pen.c; LI = c.LI
    S, H, n, ud, hd = J['S'], J['H'], J['n'], J['ud'], J['hd']
    ax = H - S
    # cuello + torso
    pen.paint(tube(S + ud * (-0.02), S + (hd - S) * 0.78, 0.115, 0.10, caps=False))
    S_ = np.linspace(-0.12, 1.02, 30)
    prof = [(-0.12, .15), (0.0, .33), (0.10, .38), (0.25, .35), (0.45, .28), (0.70, .26), (0.9, .29), (1.02, .30)]
    W_ = np.interp(S_, [a for a, b in prof], [b for a, b in prof])
    kk = np.hanning(9)[1:-1]; kk /= kk.sum(); W_ = np.convolve(np.pad(W_, 3, mode='edge'), kk, mode='valid')
    cc = np.array([S + ax * s for s in S_])
    pen.paint([('p', np.vstack([cc + n * W_[:, None], (cc - n * W_[:, None])[::-1]]))])
    P_ = lambda s, off: S + ax * s + n * off
    if np.linalg.norm(ax) > 0.35:                                       # con el torso muy escorzado no se pintan las costillas (no caben)
        for sg in (1, -1):
            pen.line(smooth_curve([P_(0.30, sg * 0.03), P_(0.30, sg * 0.15), P_(0.24, sg * 0.28)]))
            for s_ in (0.46, 0.57, 0.68):
                pen.line([P_(s_, sg * 0.03), P_(s_, sg * 0.11)], w=LI)
        pen.line([P_(0.38, 0), P_(0.78, 0)], w=LI * 0.9)
    pen.line(smooth_curve([P_(0.05, -0.12), P_(0.0, 0.0), P_(0.05, 0.12)]), w=LI * 0.9)
    # pantalon (cintura)
    pts_h = []
    for sg in (1, -1):
        for s2, wd in ((0.80, 0.27), (1.0, 0.31)):
            pts_h.append(S + ax * s2 + n * sg * wd)
    for sd in 'RL':
        hp = J[sd + '_leg'][0]
        for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False):
            pts_h.append(hp + 0.21 * np.array([np.cos(a_), np.sin(a_)]))
    pen.paint([('p', cv2.convexHull(np.array(pts_h, np.float32)).reshape(-1, 2))], SHORTS)
    pen.line([P_(1.0, -0.30), P_(1.0, 0.30)], w=LI * 0.9)
    # cabeza
    v = (hd - S) / (np.linalg.norm(hd - S) + 1e-9)
    th_ = np.linspace(0, 2 * np.pi, 80, endpoint=False); pv = np.array([-v[1], v[0]]); hc = hd + v * 0.035
    pen.paint([('p', hc + np.outer(0.30 * np.sin(th_), v) + np.outer(0.255 * np.cos(th_), pv))])
    # brazos
    for sd in 'RL':
        sh, e, w = J[sd + '_arm']
        shapes = [('c', sh, 0.145)] + tube(sh, e, 0.125, 0.095, bulge=0.15, peak=0.42) + tube(e, w, 0.095, 0.08, bulge=0.12, peak=0.3)
        shapes.append(('c', w + (w - e) / (np.linalg.norm(w - e) + 1e-9) * 0.05, 0.10))
        pen.paint(shapes)
        nn1 = rot((e - sh) / (np.linalg.norm(e - sh) + 1e-9), 90)
        pen.line(smooth_curve([sh + (e - sh) * 0.25 + nn1 * 0.03, sh + (e - sh) * 0.5 + nn1 * 0.05, sh + (e - sh) * 0.8 + nn1 * 0.02]), w=LI * 0.9)
        nn2 = rot((w - e) / (np.linalg.norm(w - e) + 1e-9), 90)
        pen.line(smooth_curve([e + (w - e) * 0.15 - nn2 * 0.03, e + (w - e) * 0.45 - nn2 * 0.04, e + (w - e) * 0.8 - nn2 * 0.015]), w=LI * 0.9)
    # piernas (lo mas cercano a la camara, encima de todo): primero los MUSLOS con el pantalon y despues las ESPINILLAS y las zapatillas, que van por delante
    for sd in 'RL':
        hp, kn, an, fd = J[sd + '_leg']
        pen.paint(tube(hp, kn, 0.19, 0.13, bulge=0.07, peak=0.4))
        pen.line(smooth_curve([hp + (kn - hp) * 0.45, hp + (kn - hp) * 0.7, hp + (kn - hp) * 0.92]), w=LI * 0.9)
        end = hp + (kn - hp) * 0.50
        tv = (end - hp) / (np.linalg.norm(end - hp) + 1e-9); tn = np.array([-tv[1], tv[0]])
        pts = [end + tn * s * 0.20 for s in (1, -1)] + [hp + 0.21 * np.array([np.cos(a_), np.sin(a_)]) for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False)]
        pen.paint([('p', cv2.convexHull(np.array(pts, np.float32)).reshape(-1, 2))], SHORTS)
        pen.line([end + tn * 0.19, end - tn * 0.19], w=LI * 0.9)
    for sd in 'RL':
        hp, kn, an, fd = J[sd + '_leg']
        shapes = tube(kn, an, 0.13, 0.075, bulge=0.2, peak=0.3)
        fc = an + np.array([0.0, shoe_dy])
        th2 = np.linspace(0, 2 * np.pi, 28, endpoint=False)
        shapes.append(('p', np.stack([fc[0] + 0.115 * np.cos(th2), fc[1] + 0.09 * np.sin(th2)], 1)))
        pen.paint(shapes)


def manos_frente(J):
    ex = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        h = w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05
        ex.append(lambda pen, h=h: draw_grip_front(pen, h, BAR_F))
    return ex


def flechas_frente(subiendo, y0):
    def f(pen):
        if not CFG['arrows']:
            return
        for sg in (1, -1):
            a, b = (y0, y0 + 0.75) if subiendo else (y0 + 0.75, y0)
            draw_line_arrow(pen, (sg * 1.02, a), (sg * 1.02, b))
    return f


def reloj(cx, cy, r=0.27):
    def f(pen):
        c = np.array([cx, cy]); th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(90) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return f


def guia_frente(y):
    def f(pen):
        for sg in (1, -1):
            dashed(pen, (sg * 0.62, y), (sg * 1.12, y), n=7)
    return f


# ================================================================= escena
PW = int(CFG['pw'])
poses_side = [pose_side(J3) for J3 in STATES]
Js_side = [build_side(p) for p in poses_side]
for J in Js_side:
    J['view'] = 'side'
Js_front = [pose_front(J3) for J3 in STATES]

# escala comun: la que cabe en los dos paneles
pts_s = np.vstack([all_points(J) for J in Js_side] + [np.array([[-0.95, 0.0], [1.95, BAR + 0.1]])])
pts_f = np.vstack([pts_front(J) for J in Js_front] + [np.array([[-1.25, 0.0], [1.25, BAR + 0.25]])])
m = CFG['margin']
y0, y1 = -0.25, BAR + 0.25
cy = (y0 + y1) / 2
sc = min(CH * SS / ((y1 - y0) + 2 * m),
         PW * SS / ((pts_s[:, 0].max() - pts_s[:, 0].min()) + 2 * m),
         PW * SS / ((pts_f[:, 0].max() - pts_f[:, 0].min()) + 2 * m))
cvS = PCanvas((pts_s[:, 0].max() + pts_s[:, 0].min()) / 2, cy, sc, PW)
cvF = PCanvas((pts_f[:, 0].max() + pts_f[:, 0].min()) / 2, cy, sc, PW)


def suelo(img, cv_):
    fy = cv_.C((0, -0.055))[1]
    cv2.line(img, (0, int(fy)), (img.shape[1], int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)


def panel_frente(i):
    img = np.full((CH * SS, PW * SS, 3), 255, np.uint8); pen = Pen(cvF, img); J = Js_front[i]; J3 = STATES[i]
    suelo(img, cvF)
    for x in (-1.25, 1.25):
        pen.line([(x, 0.0), (x, BAR + 0.25)], w=cvF.LW * 1.3)
    pen.line([(-1.25, BAR_F), (1.25, BAR_F)], w=cvF.LW * 1.3)
    hold = (i == 2)
    if hold and CFG['guide']:
        guia_frente(SY)(pen)
    if i == 0:
        figura.draw_front(pen, dict(J, R_leg=J['R_leg'], L_leg=J['L_leg']))
    else:
        draw_front_lever(pen, J)
    for ex in manos_frente(J):
        ex(pen)
    if i == 1:
        flechas_frente(True, J['S'][1] - 1.15)(pen)
    if i == 3:
        flechas_frente(False, J['S'][1] - 1.15)(pen)
    if hold and CFG['clock']:
        reloj(0.86, SY - 0.80)(pen)
    return cv2.resize(img, (PW, CH), interpolation=cv2.INTER_AREA)


def panel_perfil(i):
    img = np.full((CH * SS, PW * SS, 3), 255, np.uint8); pen = Pen(cvS, img); J = Js_side[i]
    suelo(img, cvS)
    if i == 2 and CFG['guide']:
        guia_perfil(SY)(pen)
    draw_side(pen, J)
    if i != 0:                                                         # colgado el brazo tapa la cara: sin nariz ni ojo encima del brazo
        cara(J)(pen)
    for ex in punos_perfil(J):
        ex(pen)
    return cv2.resize(img, (PW, CH), interpolation=cv2.INTER_AREA)


def etiqueta(img, txt, x):
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil)
    font = None
    for nombre in ('arial.ttf', 'segoeui.ttf', 'DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'LiberationSans-Regular.ttf'):
        try:
            font = ImageFont.truetype(nombre, 11); break
        except Exception:
            pass
    font = font or ImageFont.load_default()
    w = d.textlength(txt, font=font)
    d.text((x - w / 2, 4), txt, fill=(135, 135, 135), font=font)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


frames = []
for i in range(4):
    f_ = np.hstack([panel_frente(i), panel_perfil(i)])
    f_ = cv2.resize(f_, (CW, CH), interpolation=cv2.INTER_AREA) if f_.shape[1] != CW else f_
    cv2.line(f_, (PW, 12), (PW, CH - 14), FLOOR, 1, cv2.LINE_AA)           # separador de los dos paneles
    if CFG['labels']:
        f_ = etiqueta(f_, 'DE FRENTE', PW // 2); f_ = etiqueta(f_, 'DE PERFIL', PW + PW // 2)
    frames.append(f_)

base = OUT + 'tuck-lever-bar'
if CFG['png']:
    for i, im in enumerate(frames):
        cv2.imwrite(f'{base}_{i + 1}.png', im)
    cv2.imwrite(base + '_par.png', np.hstack(frames))
rgb = [Image.fromarray(cv2.cvtColor(f_, cv2.COLOR_BGR2RGB)) for f_ in frames]
mont = Image.new('RGB', (CW, CH * len(rgb)))
for i, r_ in enumerate(rgb):
    mont.paste(r_, (0, CH * i))
pal = mont.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
pil = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in rgb]
pil[0].save(base + '.gif', save_all=True, append_images=pil[1:], duration=[1200, 800, int(CFG['hold']), 800], loop=0, optimize=True, disposal=1)
print('GIF', base + '.gif', os.path.getsize(base + '.gif') // 1024, 'KB', len(pil), 'frames')


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (sobre lo DIBUJADO en el panel frontal)
def codo(J, sd):
    s, e, w_ = J[sd + '_arm']; a, b = s - e, w_ - e
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


def medidas(J):
    sh_y = (J['R_arm'][0][1] + J['L_arm'][0][1]) / 2
    wr_y = (J['R_arm'][2][1] + J['L_arm'][2][1]) / 2
    kn_y = (J['R_leg'][1][1] + J['L_leg'][1][1]) / 2
    an_y = (J['R_leg'][2][1] + J['L_leg'][2][1]) / 2
    return dict(hang=(wr_y - sh_y) / SW, rod=(sh_y - kn_y) / SW, tob=(sh_y - an_y) / SW,           # >0: la rodilla / el tobillo estan POR DEBAJO del hombro
                codos=(codo(J, 'R'), codo(J, 'L')), tob_min=min(J['R_leg'][2][1], J['L_leg'][2][1]))


mm = [medidas(J) for J in Js_front]
for nombre, m_, J3 in zip(('colgado (A)', 'a medio camino (B)', 'tuck lever (C)'), mm[:3], STATES[:3]):
    gap = max(m_['rod'], m_['tob'])
    ok = max(m_['rod'], m_['tob']) <= TUCKLEVER_KNEE_MAX_GAP_FACTOR
    esp = float(np.degrees(np.arctan2(abs(J3['S'][1] - J3['H'][1]), abs(J3['S'][2] - J3['H'][2]))))
    print(f"{nombre}: muñecas {m_['hang']:.2f} anchos sobre los hombros (la app exige > {HANG_MARGIN_FACTOR}); codos {m_['codos'][0]:.0f}/{m_['codos'][1]:.0f}°; "
          f"rodilla {-m_['rod']:+.2f} / tobillo {-m_['tob']:+.2f} anchos sobre el hombro (al armar vale >= -{TUCKLEVER_KNEE_MAX_GAP_FACTOR}) -> "
          f"{'CUENTA' if ok else 'no cuenta'}; espalda a {esp:.0f}° de la horizontal")
for m_ in mm[:3]:
    assert m_['hang'] > HANG_MARGIN_FACTOR, 'las muñecas deben quedar por encima de los hombros (colgado)'
    assert min(m_['codos']) > 165, 'brazos estirados'
assert mm[0]['rod'] > TUCKLEVER_KNEE_LOOSE_MAX_GAP_FACTOR and mm[0]['tob'] > TUCKLEVER_KNEE_LOOSE_MAX_GAP_FACTOR, 'colgado: no debe contar como tuck lever'
assert mm[1]['rod'] > TUCKLEVER_KNEE_MAX_GAP_FACTOR and mm[1]['tob'] > TUCKLEVER_KNEE_MAX_GAP_FACTOR, 'a medio camino: aun no debe contar'
assert mm[2]['rod'] <= TUCKLEVER_KNEE_MAX_GAP_FACTOR and mm[2]['tob'] <= TUCKLEVER_KNEE_MAX_GAP_FACTOR, 'tuck lever: rodillas y tobillos por encima del hombro'
assert mm[0]['tob_min'] > 0.3, 'colgado: los pies tocan el suelo'
print('OK: colgado y medio camino NO cuentan; el tuck lever (rodillas y tobillos sobre el hombro, brazos estirados) SI, igual que checkTuckLeverPosture')
