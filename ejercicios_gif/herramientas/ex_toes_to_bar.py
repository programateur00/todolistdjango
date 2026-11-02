"""Toes to bar (pies a la barra), vista FRONTAL, colgado de la barra con agarre prono algo mas ancho que los hombros.
Mismo montaje (barra + postes), muñeco, manos agarradas y vista que ex_dominadas.py / ex_dead_hang.py / ex_dominadas_escapulares.py.
La app usa su propio contador "toestobar" (slug toes-to-bar, processToesToBar en workout.js), que solo mira la ALTURA de los pies
(el tobillo o la punta mas alta de cada lado) frente a la barra (muñecas) y la cadera, en unidades de torso (vale de frente o de perfil;
aqui, de frente como el resto de ejercicios de barra):
  - ABAJO (colgado, brazos estirados, piernas colgando con las rodillas apenas flexionadas): pies a >= TOESTOBAR_DOWN_BELOW_HIP = 0.60 torsos POR DEBAJO de la cadera,
  - ARRIBA (la repeticion cuenta): pies a <= TOESTOBAR_UP_BELOW_BAR = 0.45 torsos por debajo de la barra (o por encima). Los hombros bajan
    (omoplatos hacia abajo), las piernas (casi rectas) suben por DELANTE del cuerpo hasta que las puntas de los pies tocan la barra,
  - a medio camino (piernas a mitad de subida, elevacion de piernas / rodillas) NO cuenta: esa es la diferencia con un toes to bar.
De frente las piernas suben hacia la camara: se ven ACORTADAS por la perspectiva (y tapan el tronco) y las puntas de los pies quedan
en la barra, a los lados de la cabeza, entre las manos. Por eso el GIF tiene 4 fotogramas: colgado -> piernas subiendo (flechas grises
hacia arriba) -> pies EN la barra (circulos grises en el contacto) -> piernas bajando (flechas grises hacia abajo).
La geometria se RESUELVE: cuanto se acortan las piernas arriba sale de que la punta del pie quede en la barra. Al final se comprueban los
umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_toes_to_bar.py [carpeta_salida] [clave=valor ...]   (genera toes-to-bar.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
CFG = dict(grip=0.58, rA=0.998, rC=0.975, shrugA=0.14, shrugC=-0.07, spreadA=2, shinA=0.62, tilt=7, feet_up=0.30, tipC=0.04,
           pitchB=33, margin=0.5, arrow_x=1.02, arrows=1, ring=1, ring_r=0.17)
# grip: mitad de la separacion de las manos (0.58 = un poco mas ancha que los hombros, igual que dead hang / escapulares)
# rA / rC: fraccion del brazo estirado (1 = recto del todo) colgado / arriba; shrugA / shrugC: hombros hacia las orejas (+) / bajados (-)
# spreadA: grados de apertura de las piernas colgando; shinA: acortamiento de la espinilla colgado (rodillas algo flexionadas hacia atras, como en dead hang: asi los pies no tocan el suelo); tilt: grados que se abren las piernas hacia fuera al subir (los pies caen a los lados de la cabeza)
# feet_up: cuanto sobresale la punta del pie por encima del tobillo cuando el pie apunta a la barra; tipC: hueco entre la punta y la barra
# pitchB: grados sobre la horizontal de las piernas en el fotograma intermedio (0 = horizontales hacia la camara, 90 = verticales)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
TOESTOBAR_UP_BELOW_BAR = 0.45
TOESTOBAR_DOWN_BELOW_HIP = 0.60
TOESTOBAR_HANG_MARGIN = 0.06
REACH = L_UA + L_FA
g = CFG['grip']
ANK_DY = {'A': -0.10, 'B': 0.15, 'C': CFG['feet_up']}     # la punta del pie respecto al tobillo (en y): colgando, a medio camino, apuntando a la barra


def hip_for(reach, shrug):
    """cadera que deja el brazo a la fraccion 'reach' de su longitud: hombro = cadera + torso(1) + encogimiento"""
    dy = np.sqrt((reach * REACH) ** 2 - (g - 0.34) ** 2)
    return BAR - dy - 1.0 - shrug


def pose(hip_y, shrug, th, sc, tilt):
    """th: grados del muslo/espinilla medidos desde la horizontal (90 = vertical); sc: acortamiento de la pierna por la perspectiva
    (piernas que suben HACIA la camara se ven mas cortas); tilt: apertura hacia fuera"""
    return dict(view='front', ground=False, hip=(0, hip_y), torso=90, head=90, shrug=shrug,
                R_arm=('ik', (g, BAR), 'cw'), L_arm=('ik', (-g, BAR), 'ccw'),
                R_leg=('fk', th - tilt, th - tilt), L_leg=('fk', 180 - th + tilt, 180 - th + tilt),
                thigh_R=sc, shin_R=sc, thigh_L=sc, shin_L=sc)


hipA = hip_for(CFG['rA'], CFG['shrugA'])
hipC = hip_for(CFG['rC'], CFG['shrugC'])
hipB = hip_for(0.99, 0.0)
A = pose(hipA, CFG['shrugA'], 270 + 0, 1.0, 0)
A['R_leg'] = ('fk', 270 + CFG['spreadA'], 270 + CFG['spreadA'])           # colgando, casi rectas, algo abiertas
A['L_leg'] = ('fk', 270 - CFG['spreadA'], 270 - CFG['spreadA'])
A['shin_R'] = A['shin_L'] = CFG['shinA']
# B: piernas a mitad de subida: pitchB grados sobre la horizontal, acortadas por el escorzo (la longitud en y es sen(pitch))
scB = float(np.sin(np.deg2rad(CFG['pitchB'])))
B = pose(hipB, 0.0, 90, scB, CFG['tilt'] * 0.6)
# C: se RESUELVE el acortamiento de las piernas para que la punta del pie (tobillo + feet_up) quede justo bajo la barra
lo, hi = 0.3, 1.2
for _ in range(60):
    mid = (lo + hi) / 2
    J_ = build_front(pose(hipC, CFG['shrugC'], 90, mid, CFG['tilt']))
    top = max(J_['R_leg'][2][1], J_['L_leg'][2][1]) + ANK_DY['C']
    if top < BAR - CFG['tipC']:
        lo = mid
    else:
        hi = mid
SC_C = hi
C = pose(hipC, CFG['shrugC'], 90, SC_C, CFG['tilt'])


# ---------------------------------------------------------------- extras de dibujo
def manos(pose_):
    """Manos agarrando la barra (agarre prono visto de frente), igual que ex_dominadas.py."""
    J = build_front(pose_); hs = []
    for sd in 'RL':
        sh, e, w_ = J[sd + '_arm']
        hs.append(w_ + (w_ - e) / (np.linalg.norm(w_ - e) + 1e-9) * 0.05)
    return [lambda pen, h=h: draw_grip_front(pen, h, BAR) for h in hs]


def piernas_delante(pose_, estado):
    """De frente, las piernas que suben pasan POR DELANTE del tronco (figura.draw_front pinta las piernas primero y el tronco encima):
    se repintan despues del cuerpo, con el pantalon en la parte alta del muslo y la zapatilla por ENCIMA del tobillo (la punta apunta a la barra)."""
    J = build_front(pose_)

    def f(pen):
        LI = pen.c.LI
        for sd in 'RL':
            hp, kn, an, fd = J[sd + '_leg']
            shapes = tube(hp, kn, 0.19, 0.13, bulge=0.07, peak=0.4) + tube(kn, an, 0.13, 0.075, bulge=0.2, peak=0.3)
            fc = an + np.array([0.0, ANK_DY[estado] * 0.62])                  # centro de la zapatilla
            th = np.linspace(0, 2 * np.pi, 28, endpoint=False)
            shapes.append(('p', np.stack([fc[0] + 0.115 * np.cos(th), fc[1] + 0.095 * np.sin(th)], 1)))
            pen.paint(shapes)
            nn = rot((kn - hp) / (np.linalg.norm(kn - hp) + 1e-9), 90)
            pen.line(smooth_curve([hp + (kn - hp) * 0.45, hp + (kn - hp) * 0.7, hp + (kn - hp) * 0.92]), w=LI * 0.9)
            # pantalon: mitad alta del muslo
            end = hp + (kn - hp) * 0.50
            tv = (end - hp) / (np.linalg.norm(end - hp) + 1e-9); tn = np.array([-tv[1], tv[0]])
            pts = [end + tn * s * 0.20 for s in (1, -1)] + [hp + 0.21 * np.array([np.cos(a_), np.sin(a_)]) for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False)]
            pen.paint([('p', cv2.convexHull(np.array(pts, np.float32)).reshape(-1, 2))], SHORTS)
            pen.line([end + tn * 0.19, end - tn * 0.19], w=LI * 0.9)
    return f


def flechas(subiendo):
    """Flechas grises a cada lado del cuerpo: las piernas suben (flecha arriba) o bajan (flecha abajo)."""
    def f(pen):
        if not CFG['arrows']:
            return
        y0 = hipB - 0.35
        for sg in (1, -1):
            a, b = (y0, y0 + 0.75) if subiendo else (y0 + 0.75, y0)
            draw_line_arrow(pen, (sg * CFG['arrow_x'], a), (sg * CFG['arrow_x'], b))
    return f


def circulos_contacto(pose_):
    """Circulos grises donde la punta de cada pie toca la barra."""
    J = build_front(pose_)

    def f(pen):
        if not CFG['ring']:
            return
        for sd in 'RL':
            an = J[sd + '_leg'][2]
            c = np.array([an[0], BAR - 0.05])
            th = np.linspace(0, 2 * np.pi, 48)
            pen.line(np.array([c + CFG['ring_r'] * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
    return f


exA = manos(A)
exB1 = [piernas_delante(B, 'B')] + manos(B) + [flechas(True)]
exC = [piernas_delante(C, 'C')] + manos(C) + [circulos_contacto(C)]
exB2 = [piernas_delante(B, 'B')] + manos(B) + [flechas(False)]
render_scene([A, B, C, B], OUT + 'toes-to-bar', props=RIG, durations=[1100, 700, 1300, 700], margin=CFG['margin'],
             extras=[exA, exB1, exC, exB2])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def elbow_deg(J, sd):
    s, e, w_ = J[sd + '_arm']
    a, b = s - e, w_ - e
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


def medidas(pose_, estado):
    J = build_front(pose_)
    torso = float(np.linalg.norm(J['S'] - J['H']))
    foot_y = np.mean([J[sd + '_leg'][2][1] + max(ANK_DY[estado], 0.0) if estado != 'A' else J[sd + '_leg'][2][1] for sd in 'RL'])   # el punto mas alto de cada lado (tobillo o punta)
    sh_y = (J['R_arm'][0][1] + J['L_arm'][0][1]) / 2
    wr_y = (J['R_arm'][2][1] + J['L_arm'][2][1]) / 2
    return J, dict(torso=torso, foot=foot_y, wrist=wr_y, hip=J['H'][1], hang=(wr_y - sh_y) / torso,
                   up_limit=wr_y - TOESTOBAR_UP_BELOW_BAR * torso, down_limit=J['H'][1] - TOESTOBAR_DOWN_BELOW_HIP * torso)


JA, mA = medidas(A, 'A'); JB, mB = medidas(B, 'B'); JC, mC = medidas(C, 'C')
print(f"acortamiento de las piernas arriba = {SC_C:.2f} (se resuelve para que la punta del pie llegue a la barra)")
for nombre, m, J in (('abajo   (A)', mA, JA), ('subiendo (B)', mB, JB), ('arriba  (C)', mC, JC)):
    estado = 'ARRIBA' if m['foot'] >= m['up_limit'] else ('ABAJO' if m['foot'] <= m['down_limit'] else 'intermedio (no cuenta)')
    dh = m['hip'] - m['foot']
    print(f"{nombre}: pies a {BAR - m['foot']:.2f} torsos bajo la barra y {abs(dh):.2f} {'bajo' if dh >= 0 else 'SOBRE'} la cadera -> {estado}; "
          f"muñecas {m['hang']:.2f} torsos sobre los hombros (la app exige > {TOESTOBAR_HANG_MARGIN}); codos {elbow_deg(J,'R'):.0f}/{elbow_deg(J,'L'):.0f}°")
print(f"limite arriba: pies a <= {TOESTOBAR_UP_BELOW_BAR} torsos bajo la barra | limite abajo: pies >= {TOESTOBAR_DOWN_BELOW_HIP} torsos bajo la cadera")
assert mA['foot'] <= mA['down_limit'], 'colgado: los pies no estan lo bastante bajo la cadera'
assert min(JA['R_leg'][2][1], JA['L_leg'][2][1]) > 0.5, 'colgado: los pies tocan el suelo'
assert mC['foot'] >= mC['up_limit'], 'arriba: los pies no llegan a la barra'
assert mB['down_limit'] < mB['foot'] < mB['up_limit'], 'a medio camino debe ser zona intermedia (no cuenta)'
for m in (mA, mB, mC):
    assert m['hang'] > TOESTOBAR_HANG_MARGIN, 'las muñecas deben quedar por encima de los hombros (colgado)'
print('OK: abajo, intermedio y arriba coinciden con los umbrales del contador')
