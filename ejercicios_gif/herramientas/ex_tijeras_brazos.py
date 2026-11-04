"""Tijeras de brazos (arm scissors / cross-body arm swing), DE FRENTE. Mismo muñeco, suelo y flechas grises que el resto de GIFs de
ejercicios_gif (figura.py). SIN cara (sin nariz, ojo ni oreja: draw_front solo dibuja un ovalo liso).

Tecnica (Motra, Physitrack «Scarecrow», Planfit): de pie, pies a la anchura de caderas, brazos extendidos a los lados a la altura de los hombros
(una T). Se llevan los dos brazos hacia delante y se CRUZAN por delante del pecho, como un abrazo (codos casi rectos, un brazo pasa por encima
del otro); se vuelve a abrir en T y se repite alternando que brazo queda por encima. Un vaiven completo T -> cruzado -> T = 1 repeticion.

Es DE FRENTE a proposito: es la vista que exige el contador de la app (counter_key="armscissors", processArmScissors en workout.js,
migracion 0035). Las comprobaciones del final usan esos mismos umbrales (ARMSCISSORS_*) y simulan su maquina de estados
(null -> center [brazos extendidos] -> crossed [las dos muñecas cruzadas] -> center = 1 rep).

Fotogramas (8, en bucle): T -> barrido hacia dentro (brazos acortados por el escorzo, flechas grises hacia dentro) -> CRUZADO con el brazo
derecho de la imagen por encima -> barrido hacia fuera (flechas hacia fuera) -> T -> barrido -> CRUZADO con el izquierdo por encima -> barrido.
Uso: python ex_tijeras_brazos.py [carpeta_salida] [clave=valor ...]   (genera arm-scissors.gif + PNG de cada fotograma;
usar una carpeta temporal, no ejercicios_gif)
Parametros: open_ang (inclinacion de los brazos en T, 0 = horizontal), cross_ua/cross_fa (angulos de brazo/antebrazo al cruzar, 180 = horizontal),
cross_k (escorzo de los brazos al cruzar, 1 = longitud entera), mid_k (escorzo en el barrido), arrows=0, margin, dur*.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(open_ang=2.0, mid_ang=6.0, mid_k=0.62, cross_ua=203.0, cross_fa=191.0, cross_k=0.80, arrows=1, arr_dy=0.36, arr_len=0.46,
           margin=0.42, durT=900, durM=300, durX=900, hip_y=2.0)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (ARMSCISSORS_*)
MIN_REACH = 0.35           # ARMSCISSORS_MIN_REACH_FACTOR: muñeca a >= esto x ancho de hombros de su hombro = brazo extendido
CROSS_MIN = 0.22           # ARMSCISSORS_CROSS_MIN_FRACTION: cada muñeca recorre >= esto de la distancia al hombro contrario = cruzado
CROSS_EXIT = 0.10          # ARMSCISSORS_CROSS_EXIT_FRACTION: las dos por debajo de esto = vuelta al centro (cierra la repeticion)

STAND = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268))
mir = lambda a: 180 - a


def pose(kind):
    """kind: 'open' (T) | 'mid' (barrido, brazos hacia la camara -> acortados) | 'crossR' / 'crossL' (cruzado; la letra = brazo que queda ENCIMA)"""
    d = dict(view='front', hip=(0, CFG['hip_y']), torso=90, head=90, **STAND)
    if kind == 'open':
        a = CFG['open_ang']
        return dict(d, R_arm=('fk', a, a), L_arm=('fk', mir(a), mir(a)))
    if kind == 'mid':
        a, k = CFG['mid_ang'], CFG['mid_k']
        return dict(d, R_arm=('fk', a, a), L_arm=('fk', mir(a), mir(a)),
                    fore_R_ua=k, fore_R_fa=k, fore_L_ua=k, fore_L_fa=k)
    u, f, k = CFG['cross_ua'], CFG['cross_fa'], CFG['cross_k']
    # el brazo derecho de la imagen cruza hacia la izquierda (angulos ~190-205) y el izquierdo es su espejo
    return dict(d, R_arm=('fk', u, f), L_arm=('fk', mir(u), mir(f)),
                fore_R_ua=k, fore_R_fa=k, fore_L_ua=k, fore_L_fa=k)


SEQ = ['open', 'mid', 'crossR', 'mid', 'open', 'mid', 'crossL', 'mid']
FRAMES = [pose('open' if s == 'open' else 'mid' if s == 'mid' else 'cross') for s in SEQ]


def final_J(fr):
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


# ---------------------------------------------------------------- extras
def brazo_encima(J, side):
    """repinta por ENCIMA el brazo `side`: draw_front pinta siempre primero el derecho y luego el izquierdo, asi que el izquierdo queda encima
    al cruzar; para el fotograma con el derecho por encima se repinta el derecho (mismas formas y rayitas que draw_front.arm)"""
    def draw(pen):
        sh, e, w = J[side + '_arm']; LI = pen.c.LI
        shapes = [('c', sh, 0.145)] + tube(sh, e, 0.125, 0.095, bulge=0.15, peak=0.42) + tube(e, w, 0.095, 0.08, bulge=0.12, peak=0.3)
        shapes.append(('c', w + (w - e) / (np.linalg.norm(w - e) + 1e-9) * 0.05, 0.10))
        pen.paint(shapes)
        nn1 = rot((e - sh) / (np.linalg.norm(e - sh) + 1e-9), 90)
        pen.line(smooth_curve([sh + (e - sh) * 0.25 + nn1 * 0.03, sh + (e - sh) * 0.5 + nn1 * 0.05, sh + (e - sh) * 0.8 + nn1 * 0.02]), w=LI * 0.9)
        nn2 = rot((w - e) / (np.linalg.norm(w - e) + 1e-9), 90)
        pen.line(smooth_curve([e + (w - e) * 0.15 - nn2 * 0.03, e + (w - e) * 0.45 - nn2 * 0.04, e + (w - e) * 0.8 - nn2 * 0.015]), w=LI * 0.9)
    return draw


def flechas(J, inward):
    """flechas grises horizontales sobre cada brazo: hacia dentro (barrido hacia el cruce) o hacia fuera (de vuelta a la T)"""
    def draw(pen):
        if not CFG['arrows']:
            return
        y = J['S'][1] + CFG['arr_dy']
        for sg in (1, -1):
            xw = abs(J['R_arm'][2][0])                       # muñeca en el barrido: la flecha queda sobre el brazo, hacia el lado de la mano
            x_far, x_near = xw + 0.30, xw + 0.30 - CFG['arr_len']
            a, b = (x_far, x_near) if inward else (x_near, x_far)
            draw_line_arrow(pen, (sg * a, y), (sg * b, y))
    return draw


extras = []
for i, s in enumerate(SEQ):
    if s == 'mid':
        extras.append([flechas(JF[i], inward=(SEQ[i - 1] == 'open'))])
    elif s == 'crossR':
        extras.append([brazo_encima(JF[i], 'R')])
    else:
        extras.append(None)

allp = np.vstack([pts_front(J) for J in JF])
xm = max(abs(allp[:, 0]).max(), 0) + 0.15
durs = [{'open': CFG['durT'], 'mid': CFG['durM'], 'crossR': CFG['durX'], 'crossL': CFG['durX']}[s] for s in SEQ]
imgs = render_scene(FRAMES, OUT + 'arm-scissors', durations=[int(x) for x in durs], margin=CFG['margin'],
                    bbox_extra=(-xm, 0.0, xm, allp[:, 1].max() + 0.3), extras=extras)


# ---------------------------------------------------------------- comprobacion contra workout.js (processArmScissors)
def to_img(p, aspect):
    """coordenadas matematicas -> imagen normalizada (0..1) de un encuadre de ancho/alto = aspect; el muñeco ocupa ~80 % del alto"""
    s = 0.8 / (allp[:, 1].max() - allp[:, 1].min())
    return np.array([0.5 + p[0] * s / aspect, 0.9 - (p[1] - allp[:, 1].min()) * s])


def medidas(J, asp):
    g = lambda sd: [to_img(q, asp) for q in J[sd + '_arm']]
    (lS, lE, lW), (rS, rE, rW) = g('L'), g('R')                   # L = izquierda de la IMAGEN (x menor), como lm[L_SHOULDER] en la app
    sw = np.hypot(*(lS - rS))
    reachL, reachR = np.hypot(*(lW - lS)) / sw, np.hypot(*(rW - rS)) / sw
    crossL = (lW[0] - lS[0]) / (rS[0] - lS[0]); crossR = (rW[0] - rS[0]) / (lS[0] - rS[0])
    return dict(reachL=reachL, reachR=reachR, crossL=crossL, crossR=crossR)


def simula(M):
    """maquina de estados de processArmScissors: null -> center (brazos extendidos) -> crossed (las dos cruzadas) -> center (las dos < salida) = 1 rep"""
    state, reps = None, 0
    for m in M:
        if state is None:
            if m['reachL'] > MIN_REACH and m['reachR'] > MIN_REACH:
                state = 'center'
        elif state == 'center':
            if m['crossL'] >= CROSS_MIN and m['crossR'] >= CROSS_MIN:
                state = 'crossed'
        else:
            if m['crossL'] < CROSS_EXIT and m['crossR'] < CROSS_EXIT:
                reps += 1; state = 'center'
    return reps


for asp in (16 / 9, 4 / 3, 9 / 16):                               # camara horizontal, 4:3 y vertical (movil)
    M = [medidas(J, asp) for J in JF]
    for i, (s, m) in enumerate(zip(SEQ, M)):
        if s == 'open':
            assert m['reachL'] > MIN_REACH and m['reachR'] > MIN_REACH, f'{i + 1} T (aspecto {asp:.2f}): brazos extendidos {m}'
        if s in ('open', 'mid'):
            assert m['crossL'] < CROSS_EXIT and m['crossR'] < CROSS_EXIT, f'{i + 1} {s} (aspecto {asp:.2f}): no debe contar como cruzado {m}'
        else:
            assert m['crossL'] >= CROSS_MIN and m['crossR'] >= CROSS_MIN, f'{i + 1} {s} (aspecto {asp:.2f}): cruzado valido {m}'
    # dos vueltas: la primera arma el contador (T estable), en la segunda cada ciclo del GIF cuenta exactamente 2 cruces (uno por brazo encima)
    r1, r2 = simula(M), simula(M + M)
    assert r1 == 2 and r2 == 4, f'(aspecto {asp:.2f}) repeticiones por ciclo: {r1}, en dos ciclos: {r2} (esperado 2 y 4)'
    if asp == 16 / 9:
        for i, (s, m) in enumerate(zip(SEQ, M)):
            print(f"{i + 1} {s:7s}| cruce izq {m['crossL']:+.2f} der {m['crossR']:+.2f} (cruzado >= {CROSS_MIN}, centro < {CROSS_EXIT}) | "
                  f"alcance izq {m['reachL']:.2f} der {m['reachR']:.2f} (> {MIN_REACH})")
# pies apoyados y fijos; torso y piernas no se mueven entre fotogramas; brazos rectos en T
for J in JF:
    for sd in 'RL':
        assert abs(J[sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, 'los pies tocan el suelo'
assert all(np.allclose(J['S'], JF[0]['S']) and np.allclose(J['H'], JF[0]['H']) for J in JF), 'el torso no se mueve'
sh, e, w = JF[0]['R_arm']
assert abs(w[1] - sh[1]) < 0.08 and w[0] - sh[0] > 1.1, 'en T el brazo va horizontal a la altura del hombro'
print('OK: las tijeras de brazos coinciden con los umbrales del contador (armscissors, processArmScissors): 2 repeticiones por ciclo')
