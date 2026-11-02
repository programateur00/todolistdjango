"""Fondos en banco (bench dip), vista de PERFIL: manos apoyadas DETRAS del cuerpo en el borde de un banco, piernas estiradas
hacia delante con los talones en el suelo. Mismo muñeco, estilo y montaje que el resto de GIFs de ejercicios_gif (figura.py).
La app usa su propio contador "benchdip" (slug bench-dip, processBenchDip en workout.js), que mide en directo, con el lado mejor visto:
  - ANGULO DE CODO (hombro-codo-muñeca): ARRIBA >= DIP_UP_ANGLE_DEG = 155 (brazos estirados); ABAJO <= DIP_DOWN_ANGLE_DEG = 100 (codos a ~90).
    La repeticion cuenta al volver arriba tras haber pasado por abajo; entre 100 y 155 no cambia nada,
  - POSTURA en todos los fotogramas: muñeca por ENCIMA del tobillo >= BENCHDIP_HAND_RISE_MIN_FACTOR = 0.12 torsos,
    rodilla (cadera-rodilla-tobillo) >= BENCHDIP_KNEE_MIN_DEG = 150 (piernas estiradas) y tronco (hombro-cadera) a >= 50 grados de la horizontal.
  - (el angulo hombro-cadera-tobillo "L" solo es informativo: ya no abre ni cierra la serie).
GIF de 4 fotogramas: arriba (brazos estirados) -> bajando (flecha gris abajo, codos a medio doblar) -> abajo (codos a 90, arco gris)
-> subiendo (flecha gris arriba). Los pies NO se mueven: la cadera sube y baja pegada al borde del banco, de modo que las piernas
(largo fijo) se RESUELVEN para quedar siempre estiradas con el talon en el suelo. Al final se comprueban los umbrales del contador (assert).
Uso: python ex_fondos_banco.py [carpeta_salida] [clave=valor ...]   (genera fondos-en-banco.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(elbA=168, elbB=125, elbC=90, tA=100, tB=98, tC=96, bench=0.78, wx=0.0, edge=0.06, clear=0.20, foot=50, footF=62, kneeN=0.985, kneeF=0.975,
           farx=0.03, hand=-85, headd=-14, margin=0.45, arrows=1, arc=0, arrow_dx=0.72, arc_r=0.24)
# elbA/elbB/elbC: angulo del codo (grados) arriba / a medio camino / abajo (la app: >=155 arriba, <=100 abajo, en medio no cuenta)
# tA/tB/tC: inclinacion del tronco sobre la horizontal en cada fotograma (90 = vertical; >90 = hombros ATRAS, caderas hacia delante)
# bench: altura de la superficie del banco; edge: del centro de la muñeca al borde del banco; clear: hueco entre el borde y la espalda/gluteo arriba
# foot: angulo del pie (talon en el suelo, puntas arriba); kneeN/kneeF: fraccion de la pierna estirada (1 = recta del todo) pierna cercana / lejana
# footF: angulo del pie lejano; farx: cuanto mas atras queda el pie lejano; hand: angulo de los dedos sobre el borde; headd: giro de la cabeza respecto al tronco; arrows/arc: 0 los quita (arc=1 dibuja un arco gris en el codo)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
DIP_UP_ANGLE_DEG = 155
DIP_DOWN_ANGLE_DEG = 100
BENCHDIP_HAND_RISE_MIN_FACTOR = 0.12
BENCHDIP_KNEE_MIN_DEG = 150
BENCHDIP_TORSO_VERTICAL_MIN_DEG = 50
LEG = L_THIGH + L_SHIN
BUTT_BACK = 0.28          # cuanto sobresale hacia atras el gluteo/espalda baja respecto a la cadera (dibujo del muñeco)
SLAB_T, SLAB_W = 0.16, 0.95

# --- banco y muñecas (fijos: las manos NO se mueven) ---------------------------------------------------------------------
W = np.array([CFG['wx'], CFG['bench'] + 0.09])                    # muñeca cercana: apoyada sobre el banco
X_EDGE = W[0] + CFG['edge']                                        # borde delantero del banco
fd = dv(CFG['foot'])
YA = 0.04 + 0.10 * fd[0] + 0.07 * fd[1]                            # altura del tobillo para que el talon toque el suelo (y = 0)


def elbow_len(deg):
    a, b = L_UA, L_FA
    return float(np.sqrt(a * a + b * b - 2 * a * b * np.cos(np.deg2rad(deg))))


def place(elb, t, hx=None, xa=None):
    """Coloca el cuerpo: tronco a 't' grados; la muñeca W es fija y la distancia hombro-muñeca sale del angulo de codo 'elb'.
    Si se da hx (cadera x) se busca la altura de la cadera; si se da xa (pie, fijo) la cadera x sale de que la pierna mida lo que mide."""
    d = elbow_len(elb); best = None
    for hy in np.linspace(YA + 0.3, 2.4, 20000):
        x = hx if hx is not None else xa - np.sqrt(max(LEG ** 2 - (hy - YA) ** 2, 0))
        S = np.array([x + np.cos(np.deg2rad(t)), hy + np.sin(np.deg2rad(t))])
        e = abs(np.linalg.norm(S - W) - d)
        if best is None or e < best[0]:
            best = (e, hy, x)
    assert best[0] < 2e-3, 'no hay solucion de postura (revisa bench / tA / tB / tC)'
    return np.array([best[2], best[1]])


# arriba: la espalda/gluteo queda 'clear' por delante del borde del banco -> de ahi sale la cadera x, y de ella la x del pie (fija)
HIP_A = place(CFG['elbA'], CFG['tA'], hx=X_EDGE + BUTT_BACK + CFG['clear'])
XA = HIP_A[0] + np.sqrt(LEG ** 2 - (HIP_A[1] - YA) ** 2)           # pie cercano, fijo en los 3 estados
HIP_B = place(CFG['elbB'], CFG['tB'], xa=XA)
HIP_C = place(CFG['elbC'], CFG['tC'], xa=XA)
HIP_A2 = place(CFG['elbA'], CFG['tA'], xa=XA)                     # igual que HIP_A (mismo pie): comprobacion
assert np.allclose(HIP_A, HIP_A2, atol=5e-3)


def pose(hip, t, elb):
    S = hip + dv(t)
    tgtN = (XA, YA); tgtF = (XA - CFG['farx'], YA)
    legN = ('ik', (tgtN[0] - hip[0], tgtN[1] - hip[1]), 'ccw', CFG['foot'])
    legF = ('ik', (tgtF[0] - hip[0], tgtF[1] - hip[1]), 'ccw', CFG['footF'])
    # 'ikr' = objetivo relativo a la cadera; se acorta el objetivo para que la rodilla quede algo flexionada (como una pierna real)
    def short(sp, r):
        v = np.array(sp[1]); n = np.linalg.norm(v)
        L_ = min(n, LEG * r)
        return ('ikr', tuple(v / n * L_), sp[2], sp[3])
    return dict(view='side', f=1, ground=False, hip=tuple(hip), torso=t, head=t + CFG['headd'],
                near_arm=('ik', tuple(W), 'cw'), far_arm=('ik', (W[0] - 0.03, W[1]), 'cw'),
                near_hand=CFG['hand'], far_hand=CFG['hand'],
                near_leg=short(legN, CFG['kneeN']), far_leg=short(legF, CFG['kneeF']))


A = pose(HIP_A, CFG['tA'], CFG['elbA'])
B = pose(HIP_B, CFG['tB'], CFG['elbB'])
C = pose(HIP_C, CFG['tC'], CFG['elbC'])

# --- extras: banco (detras del muñeco: se pinta como 'props'), flechas y arco del codo -------------------------------------
x0b = X_EDGE - SLAB_W
PROPS = [('floorbar', x0b, CFG['bench'], X_EDGE, CFG['bench']),                  # tapa del banco
         ('floorbar', x0b, CFG['bench'] - SLAB_T, X_EDGE, CFG['bench'] - SLAB_T),
         ('floorbar', x0b, CFG['bench'], x0b, CFG['bench'] - SLAB_T),
         ('floorbar', X_EDGE, CFG['bench'], X_EDGE, CFG['bench'] - SLAB_T),
         ('floorbar', X_EDGE - 0.14, CFG['bench'] - SLAB_T, X_EDGE - 0.14, 0.0),      # patas
         ('floorbar', x0b + 0.14, CFG['bench'] - SLAB_T, x0b + 0.14, 0.0)]


def flecha(subiendo, ref):
    def f(pen):
        if not CFG['arrows']:
            return
        S = ref + dv(0) * 0  # ref = hombro del fotograma B
        x = S[0] + CFG['arrow_dx']; y0 = S[1] + 0.05
        a, b = (y0 - 0.75, y0) if subiendo else (y0, y0 - 0.75)
        draw_line_arrow(pen, (x, a), (x, b))
    return f


def arco_codo(pose_):
    J = build_side(pose_)

    def f(pen):
        if not CFG['arc']:
            return
        s, e, w_ = J['near_arm']
        a0, a1 = ang(s - e), ang(w_ - e)
        d = (a1 - a0 + 180) % 360 - 180
        angs = np.linspace(a0, a0 + d, 30)
        pen.line(np.array([e + CFG['arc_r'] * dv(a_) for a_ in angs]), w=pen.c.LI * 1.1, col=GREY_ARROW)
    return f


SB = HIP_B + dv(CFG['tB'])
frames = [A, B, C, B]
extras = [None, [flecha(False, SB)], [arco_codo(C)], [flecha(True, SB)]]
xs = [XA + 0.8, x0b - 0.1]
bb = (min(xs), -0.1, max(xs), (HIP_A + dv(CFG['tA']))[1] + 1.0)
render_scene(frames, OUT + 'fondos-en-banco', props=PROPS, floor=True, ground_all=False, extras=extras,
             durations=[1100, 700, 1300, 700], margin=CFG['margin'], bbox_extra=bb)


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js
def deg3(p, q, r):
    a, b = p - q, r - q
    return float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


def medir(P):
    J = build_side(P); out = {}
    torso = float(np.linalg.norm(J['S'] - J['H']))
    for sd in ('near', 'far'):
        s, e, w_ = J[sd + '_arm']; hp, kn, an, he, to = J[sd + '_leg']
        out[sd] = dict(elbow=deg3(s, e, w_), knee=deg3(hp, kn, an), rise=(w_[1] - an[1]) / torso, body=deg3(s, hp, an))
    d = J['S'] - J['H']
    out['tilt'] = float(abs(np.degrees(np.arctan2(d[1], d[0])))); out['tilt'] = out['tilt'] if out['tilt'] <= 90 else 180 - out['tilt']
    out['butt_gap'] = (J['H'][0] - BUTT_BACK) - X_EDGE            # >= 0: el gluteo no se mete en el banco
    out['drop'] = (J['S'][1])
    out['foot_y'] = min(min(J[s + '_leg'][3][1], J[s + '_leg'][4][1]) - 0.04 for s in ('near', 'far'))
    out['hip_y'] = J['H'][1]
    return out


MA, MB, MC = medir(A), medir(B), medir(C)
for nombre, m in (('arriba  (A)', MA), ('a medio (B)', MB), ('abajo   (C)', MC)):
    estado = 'ARRIBA' if m['near']['elbow'] >= DIP_UP_ANGLE_DEG else ('ABAJO' if m['near']['elbow'] <= DIP_DOWN_ANGLE_DEG else 'intermedio (no cambia de estado)')
    print(f"{nombre}: codo {m['near']['elbow']:.0f}/{m['far']['elbow']:.0f}° -> {estado}; manos {m['near']['rise']:.2f} torsos sobre el tobillo "
          f"(mín {BENCHDIP_HAND_RISE_MIN_FACTOR}); rodilla {m['near']['knee']:.0f}/{m['far']['knee']:.0f}° (mín {BENCHDIP_KNEE_MIN_DEG}); "
          f"tronco {m['tilt']:.0f}° (mín {BENCHDIP_TORSO_VERTICAL_MIN_DEG}); L (informativo) {m['near']['body']:.0f}°; hueco gluteo-banco {m['butt_gap']:.2f}; "
          f"cadera y={m['hip_y']:.2f}")
assert MA['near']['elbow'] >= DIP_UP_ANGLE_DEG and MA['far']['elbow'] >= DIP_UP_ANGLE_DEG, 'arriba: brazos no lo bastante estirados'
assert MC['near']['elbow'] <= DIP_DOWN_ANGLE_DEG and MC['far']['elbow'] <= DIP_DOWN_ANGLE_DEG, 'abajo: codos no lo bastante doblados'
assert DIP_DOWN_ANGLE_DEG < MB['near']['elbow'] < DIP_UP_ANGLE_DEG, 'a medio camino debe ser zona intermedia'
for m in (MA, MB, MC):
    for sd in ('near', 'far'):
        assert m[sd]['rise'] >= BENCHDIP_HAND_RISE_MIN_FACTOR, 'las manos deben quedar por encima de los pies'
        assert m[sd]['knee'] >= BENCHDIP_KNEE_MIN_DEG, 'piernas no estiradas'
    assert m['tilt'] >= BENCHDIP_TORSO_VERTICAL_MIN_DEG, 'tronco demasiado inclinado'
    assert abs(m['foot_y']) < 0.03, 'el talon no toca el suelo'
print('OK: arriba, intermedio y abajo coinciden con los umbrales del contador (benchdip)')
