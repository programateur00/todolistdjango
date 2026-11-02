"""Flexiones arquero (archer push-up), vista FRONTAL (de frente a la camara), SIN cara (ni nariz ni ojos ni orejas).
Mismo muñeco, estilo, suelo y grosores que el resto de GIFs de ejercicios_gif (figura.py). A diferencia de flexiones / diamante / anchas
(que van DE PERFIL y comparten contador), la app usa para este ejercicio un contador PROPIO y DE FRENTE (slug archer-push-up, migracion 0102,
counter_key "archerpushup", processArcherPushup en workout.js; de perfil no se podria: el brazo lejano queda tapado y no se ve de que lado se baja):
  - tumbado boca abajo MIRANDO a la camara, con las manos MUY separadas (mas anchas que los hombros) y los DOS brazos estirados (armar: ARCHER_PUSHUP_ARM_GATE_DEG = 140),
  - en cada repeticion UN brazo se dobla (codo <= ARCHER_PUSHUP_BENT_DEG = 130) mientras el OTRO queda estirado (>= ARCHER_PUSHUP_STRAIGHT_DEG = 140 al empezar la bajada,
    sin bajar de ARCHER_PUSHUP_STRAIGHT_LOOSE_DEG = 120 durante ella: si los dos se doblan es una flexion normal),
  - la CABEZA se va hacia la mano del brazo que baja: t = (nariz.x - muñeca_izq.x) / (muñeca_der.x - muñeca_izq.x) <= 0.3 o >= 0.7 (ARCHER_SHIFT_OFFSET = 0.2) y baja en vertical
    al menos ARCHER_SHIFT_MIN_DROP = 0.05 separaciones de muñecas; en una flexion normal queda centrada (t ~ 0.5),
  - cuenta al volver a estirar los dos brazos (>= ARCHER_PUSHUP_UP_DEG = 145). Se alterna de lado.
Por eso el GIF tiene 4 fotogramas: arriba (los dos brazos estirados, manos muy abiertas) -> abajo hacia la DERECHA (el brazo derecho se dobla, el izquierdo queda
estirado, el cuerpo y la cabeza se desplazan hacia la derecha) -> arriba -> abajo hacia la IZQUIERDA.
La geometria se RESUELVE (no se dibuja a ojo): con los hombros a nivel y las manos fijas en el suelo, el desplazamiento lateral x del cuerpo y la altura dy de los hombros
que dejan el brazo que baja con el codo doblado y el otro casi recto salen de dos ecuaciones; al final se comprueban los umbrales del contador (assert).
Uso: python ex_flexiones_arquero.py [carpeta_salida] [clave=valor ...]   (genera flexiones-arquero.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(grip=1.10, elbUp=172, elbS=168, elbB=70, hoff=0.22, hdrop=-0.06, htilt=7, fh=0.62, margin=0.22, arrows=1, fingers=1,
           durA=1200, durB=1300, sbase=0.80, sl=0.12, sr=0.15, sbulge=0.15)
# sbase: cuanto se desplaza el arranque del brazo hacia el centro de la cabeza (0.55 = bajo la cabeza); sr: radio del brazo en el hombro; sbulge: abultamiento del deltoides (hombro redondo)
# grip: semiseparacion de las manos (0.34 = ancho de hombros); elbUp: codo de los dos brazos arriba; elbS: codo del brazo que queda estirado abajo;
# elbB: codo del brazo que baja; hoff: cuanto se adelanta la cabeza hacia la mano que baja respecto al centro de los hombros; hdrop: la cabeza queda este poco por debajo
# de la linea de hombros; htilt: grados que se inclina la cabeza hacia ese lado; fh: factor de perspectiva de la cadera (el cuerpo se aleja de la camara)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
ARCHER_PUSHUP_ARM_GATE_DEG = 140
ARCHER_PUSHUP_BENT_DEG = 130
ARCHER_PUSHUP_STRAIGHT_DEG = 140
ARCHER_PUSHUP_STRAIGHT_LOOSE_DEG = 120
ARCHER_PUSHUP_UP_DEG = 145
ARCHER_SHIFT_OFFSET = 0.2
ARCHER_SHIFT_MIN_DROP = 0.05

SW = 0.34                       # medio ancho de hombros (como build_front)
WY = 0.15                       # altura de la muñeca con la palma en el suelo
G = CFG['grip']


def elbow_len(deg):
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


# ---------------------------------------------------------------- geometria (x derecha, y arriba; T = 1)
def pose_up():
    d = elbow_len(CFG['elbUp'])
    dy = np.sqrt(d * d - (G - SW) ** 2)
    return dict(x=0.0, sy=WY + dy, bent=None)


def pose_down(s):
    """baja hacia el lado s (+1 derecha, -1 izquierda): brazo que baja con codo elbB, el otro con codo elbS, hombros a nivel.
       (G - x - SW)^2 + dy^2 = B^2   (brazo que baja)     (G + x - SW)^2 + dy^2 = S^2   (brazo que queda estirado)"""
    S_, B_ = elbow_len(CFG['elbS']), elbow_len(CFG['elbB'])
    x = (S_ ** 2 - B_ ** 2) / (4 * (G - SW))
    dy = np.sqrt(B_ ** 2 - (G - x - SW) ** 2)
    return dict(x=s * x, sy=WY + dy, bent=s)


def joints(P):
    """hombros, codos, muñecas (IK) y cabeza de una pose. R = lado derecho de la imagen"""
    x, sy = P['x'], P['sy']
    J = {}
    for sd, sg in (('R', 1), ('L', -1)):
        sh = np.array([x + sg * SW, sy]); wr = np.array([sg * G, WY])
        e, w_ = ik2(sh, wr, L_UA, L_FA, 'ccw' if sg > 0 else 'cw')      # codos hacia fuera
        J[sd] = (sh, e, w_)
    sg = P['bent'] or 0
    hd = np.array([x + sg * CFG['hoff'], sy - CFG['hdrop']])
    J['hd'] = hd; J['S'] = np.array([x, sy]); J['tilt'] = sg * CFG['htilt']
    return J


# ---------------------------------------------------------------- dibujo
def dibuja(pen, P):
    """Sin contornos en los hombros: solo cabeza, tronco estrecho bajo ella y los brazos, que nacen DEBAJO de la cabeza (su arranque queda tapado por ella)."""
    J = joints(P); c = pen.c; LI = c.LI
    S = J['S']; sy = S[1]; x = P['x']; hd = J['hd']
    # cuerpo que se aleja de la camara: cadera mas abajo y mas pequeña (perspectiva), pies casi en el suelo
    hy = max(0.34, sy * CFG['fh'])
    H = np.array([x * 0.90, hy])
    # ---- piernas (muy escorzadas): dos tubos cortos hacia el suelo y las zapatillas
    for sg in (1, -1):
        hp = H + np.array([sg * 0.12, -0.04]); an = np.array([H[0] + sg * 0.13, 0.20])
        pen.paint(tube(hp, an, 0.115, 0.075, bulge=0.06, peak=0.4))
        th = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        fc = an + np.array([sg * 0.01, -0.085])
        pen.paint([('p', np.stack([fc[0] + 0.105 * np.cos(th), fc[1] + 0.055 * np.sin(th)], 1))])
    # ---- pantalon corto
    pen.paint([('p', np.array([H + (-0.27, 0.12), H + (0.27, 0.12), H + (0.25, -0.20), H + (-0.25, -0.20)]))], SHORTS)
    # ---- tronco: columna estrecha que cuelga DE LA CABEZA hasta el pantalon; su borde de arriba queda dentro del ovalo de la cabeza (no se ve)
    top = np.array([hd[0], hd[1]]); w_t = 0.21
    pen.paint([('p', np.array([top + (-w_t, 0.0), top + (w_t, 0.0), H + (0.25, 0.10), H + (-0.25, 0.10)]))])
    # ---- brazos: arrancan DEBAJO de la cabeza (el hombro se desplaza hacia el centro de la cabeza), asi no hay circulo ni recta en el hombro
    for sd in 'RL':
        sh, e, w = J[sd]
        # UNA sola silueta por brazo (no hay lineas internas): cuello->hombro (trapecio, queda bajo la cabeza) + cabeza del hombro redonda + brazo + antebrazo.
        # Como en una foto de frente: del lado de la cabeza el contorno baja suave por el trapecio, redondea en el hombro y sigue por el brazo.
        link = sh + (hd - sh) * CFG['sbase']
        shapes = tube(link, sh, CFG['sl'], CFG['sr'], caps=True)[:1] + [('c', sh, CFG['sr'])] \
            + tube(sh, e, CFG['sr'], 0.095, bulge=CFG['sbulge'], peak=0.30, caps=False)[:1] + [('c', e, 0.095 * (1 + CFG['sbulge'] * 0))] \
            + tube(e, w, 0.095, 0.08, bulge=0.12, peak=0.3)
        pen.paint(shapes)
        nn1 = rot((e - sh) / (np.linalg.norm(e - sh) + 1e-9), 90)
        pen.line(smooth_curve([sh + (e - sh) * 0.25 + nn1 * 0.03, sh + (e - sh) * 0.5 + nn1 * 0.05, sh + (e - sh) * 0.8 + nn1 * 0.02]), w=LI * 0.9)
        # mano plana en el suelo vista de frente (dedos hacia la camara)
        hc = np.array([w[0], WY - 0.075])
        pen.paint(tube(hc + np.array([-0.07, 0]), hc + np.array([0.07, 0]), 0.085, 0.085, caps=True))
        if CFG['fingers']:
            for dx_ in (-0.05, 0.0, 0.05):
                pen.line([(hc[0] + dx_, hc[1] - 0.015), (hc[0] + dx_, hc[1] - 0.075)], w=LI * 0.8)
    # ---- cabeza (oval liso, SIN cara: ni nariz ni ojos ni orejas), la ULTIMA: esta mas cerca de la camara que los brazos
    a_ = np.deg2rad(90 - J['tilt']); v = np.array([np.cos(a_), np.sin(a_)]); pv = np.array([-v[1], v[0]])
    th_ = np.linspace(0, 2 * np.pi, 80, endpoint=False)
    pen.paint([('p', hd + np.outer(0.30 * np.sin(th_), v) + np.outer(0.255 * np.cos(th_), pv))])


def flecha(P):
    """flecha gris hacia abajo, encima de la cabeza, solo cuando baja (los dos fotogramas 'abajo')"""
    def f(pen):
        if not CFG['arrows'] or not P['bent']:
            return
        J = joints(P); hx, hy = J['hd'][0], J['S'][1]
        draw_line_arrow(pen, (hx, hy + 0.86), (hx, hy + 0.46))
    return f


# ---------------------------------------------------------------- render (mismo GIF que render_scene de figura.py: 480x360, 16 colores, bucle)
UP = pose_up(); DR = pose_down(+1); DL = pose_down(-1)
FR = [UP, DR, UP, DL]
tops = [joints(p_)['S'][1] + (0.95 if p_['bent'] else 0.40) for p_ in FR]
bb = (-G - 0.30, -0.15, G + 0.30, max(tops))
cv_ = Canvas(bb, margin=CFG['margin'])
imgs = []
for P in FR:
    img = np.full((CH * SS, CW * SS, 3), 255, np.uint8)
    pen = Pen(cv_, img)
    fy = cv_.C((0, 0 - 0.055))[1]
    cv2.line(img, (0, int(fy)), (CW * SS, int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)
    dibuja(pen, P)
    flecha(P)(pen)
    imgs.append(cv2.resize(img, (CW, CH), interpolation=cv2.INTER_AREA))
base = OUT + 'flexiones-arquero'
for i, im in enumerate(imgs):
    cv2.imwrite(f'{base}_{i + 1}.png', im)
cv2.imwrite(base + '_par.png', np.hstack(imgs))
rgb = [Image.fromarray(cv2.cvtColor(f_, cv2.COLOR_BGR2RGB)) for f_ in imgs]
mont = Image.new('RGB', (CW, CH * len(rgb)))
for i, r_ in enumerate(rgb):
    mont.paste(r_, (0, CH * i))
pal = mont.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
pil = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in rgb]
pil[0].save(base + '.gif', save_all=True, append_images=pil[1:], duration=[int(CFG['durA']), int(CFG['durB'])] * 2, loop=0, optimize=True, disposal=1)
print('GIF', base + '.gif', os.path.getsize(base + '.gif') // 1024, 'KB', len(pil), 'frames')


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def codo(J, sd):
    sh, e, w_ = J[sd]; u = sh - e; v = w_ - e
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


JU = joints(UP)
print(f"arriba: codos {codo(JU,'R'):.0f}° / {codo(JU,'L'):.0f}° | hombros a y={UP['sy']:.2f} | manos a ±{G:.2f} (hombros ±{SW})")
assert codo(JU, 'R') >= ARCHER_PUSHUP_UP_DEG and codo(JU, 'L') >= ARCHER_PUSHUP_UP_DEG, 'arriba: los dos brazos estirados (>= 145, armar >= 140)'
assert G > SW * 1.5, 'manos MUY separadas (mas anchas que los hombros)'
for nombre, P, baja, queda in (('derecha', DR, 'R', 'L'), ('izquierda', DL, 'L', 'R')):
    J = joints(P)
    cb, cs = codo(J, baja), codo(J, queda)
    t = (J['hd'][0] - (-G)) / (2 * G)                      # t = (nariz.x - muñeca_izq.x) / (muñeca_der.x - muñeca_izq.x) (izq = x menor)
    tl = t if baja == 'R' else 1 - t                        # distancia a la mano que baja, normalizada (0 = encima de ella)
    drop = (JU['hd'][1] - J['hd'][1]) / (2 * G)
    print(f"baja a la {nombre}: codo que baja {cb:.0f}° (<= {ARCHER_PUSHUP_BENT_DEG}), codo estirado {cs:.0f}° (>= {ARCHER_PUSHUP_STRAIGHT_DEG}) | "
          f"cabeza t={t:.2f} (>= {0.5 + ARCHER_SHIFT_OFFSET:.1f} o <= {0.5 - ARCHER_SHIFT_OFFSET:.1f}), baja {drop:.2f} separaciones de muñecas (>= {ARCHER_SHIFT_MIN_DROP})")
    assert cb <= ARCHER_PUSHUP_BENT_DEG, 'el brazo que baja debe doblarse (<= 130)'
    assert cs >= ARCHER_PUSHUP_STRAIGHT_DEG, 'el otro brazo debe quedar estirado (>= 140, nunca < 120)'
    assert (t >= 0.5 + ARCHER_SHIFT_OFFSET + 0.03) if baja == 'R' else (t <= 0.5 - ARCHER_SHIFT_OFFSET - 0.03), 'la cabeza debe irse hacia la mano que baja'
    assert drop >= ARCHER_SHIFT_MIN_DROP * 2, 'la cabeza debe bajar en vertical'
    assert np.allclose(J['R'][2], JU['R'][2]) and np.allclose(J['L'][2], JU['L'][2]), 'las manos no se mueven'
    assert J[baja][1][1] > J[baja][0][1] - 0.2 and (J[baja][1][0] - J[baja][0][0]) * (1 if baja == 'R' else -1) > 0, 'el codo que se dobla sale hacia fuera'
print('OK: arriba y abajo (derecha/izquierda) coinciden con los umbrales de processArcherPushup')
