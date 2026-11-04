"""Movilidad lateral de cuello (inclinación lateral: oreja hacia el hombro), DE FRENTE. Mismo muñeco, suelo y flechas grises que el resto de GIFs
de ejercicios_gif (figura.py). SIN cara (sin nariz, ojo ni oreja: draw_front solo dibuja un ovalo liso).

Tecnica (ACE Fitness «Lateral Neck Flexion», Sweat, Physitrack): de pie, pies a la anchura de la cadera, brazos sueltos a los lados, hombros BAJOS y
quietos (que no suban hacia la oreja). Se acerca despacio una oreja al hombro del mismo lado, hasta notar el primer tiron, sin forzar; la cabeza se
INCLINA (no gira: la cara sigue mirando al frente) y se vuelve al centro; despues se hace lo mismo del otro lado.

Es DE FRENTE a proposito: es la vista que exige el contador de la app (counter_key="necklateral", processNeckLateral en workout.js, migracion 0034,
slug neck-lateral-mobility, mode "pose"). Cuenta un vaiven centro -> lado -> centro: la nariz se separa del punto medio de los hombros al menos
NECKLATERAL_ENTER_FACTOR (0.16 anchos de hombro) sin caer mas de NECKLATERAL_MAX_VERTICAL_FACTOR (0.12; si cae mas es «barbilla al pecho»), y los
hombros no se desplazan (NECKLATERAL_DRIFT_TOLERANCE_FACTOR 0.12). Las comprobaciones del final usan esos mismos umbrales.

Secuencia (bucle): centro -> inclinado a la DERECHA de la imagen -> centro -> inclinado a la IZQUIERDA. Flecha gris curva sobre la cabeza en los
fotogramas inclinados (`arrows=0` la quita).
Uso: python ex_movilidad_cuello.py [carpeta_salida] [clave=valor ...]   (genera neck-lateral-mobility.gif + PNG de cada fotograma;
usar una carpeta temporal, no ejercicios_gif)
Parametros: tilt (grados de inclinacion de cabeza+cuello, 22: con mas, la nariz «cae» demasiado para el umbral vertical en encuadre horizontal 16:9), arrows, arr_r, arr_span, margin, hip_y, durC (centro), durT (lado).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(tilt=22.0, arrows=1, arr_r=1.12, arr_span=24.0, margin=0.30, hip_y=2.0, durC=700, durT=1200)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (NECKLATERAL_*)
MIN_ENTER = 0.16
MAX_VERTICAL = 0.12
EXIT = 0.05
DRIFT_TOL = 0.12

STAND = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268))
ARMS_DOWN = dict(R_arm=('fk', 281, 272), L_arm=('fk', 259, 268))   # brazos sueltos, hombros quietos y bajos


def pose(kind):
    """kind: 'C' centro, 'R' inclinado hacia la derecha de la imagen, 'L' hacia la izquierda. La cabeza y el cuello giran juntos alrededor de la base
    del cuello (build_front: head = angulo del cuello->cabeza, 90 = recto); el torso, los hombros y los brazos no se tocan."""
    h = {'C': 90.0, 'R': 90.0 - CFG['tilt'], 'L': 90.0 + CFG['tilt']}[kind]
    return dict(view='front', hip=(0, CFG['hip_y']), torso=90, head=h, **STAND, **ARMS_DOWN)


SEQ = ['C', 'R', 'C', 'L']
FRAMES = [pose(k) for k in SEQ]


def final_J(fr):
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


def flecha(J, kind):
    """flecha curva gris alrededor de la base del cuello, por encima de la cabeza, en el sentido de la inclinacion"""
    def draw(pen):
        if not CFG['arrows']:
            return
        c = 90.0 + (-CFG['tilt'] if kind == 'R' else CFG['tilt'])         # direccion de la cabeza
        a0 = 90.0 + (-1 if kind == 'R' else 1) * 6
        a1 = c + (-1 if kind == 'R' else 1) * (CFG['arr_span'] - CFG['tilt'] if CFG['arr_span'] > CFG['tilt'] else 4)
        draw_arrow(pen, J['S'], CFG['arr_r'], a0, a1)
    return draw


extras = [None if k == 'C' else [flecha(JF[i], k)] for i, k in enumerate(SEQ)]

allp = np.vstack([pts_front(J) for J in JF])
ytop = max(J['hd'][1] for J in JF) + 0.34
arrow_pts = []
for i, k in enumerate(SEQ):
    if k != 'C' and CFG['arrows']:
        for a_ in np.linspace(60, 120, 7):
            arrow_pts.append(JF[i]['S'] + CFG['arr_r'] * dv(a_))
arrow_pts = np.array(arrow_pts) if len(arrow_pts) else allp
xm = max(abs(arrow_pts[:, 0]).max() + 0.15, abs(allp[:, 0]).max() + 0.1, 0.9)
durs = [int(CFG['durC'] if k == 'C' else CFG['durT']) for k in SEQ]
imgs = render_scene(FRAMES, OUT + 'neck-lateral-mobility', durations=durs, margin=CFG['margin'],
                    bbox_extra=(-xm, 0.0, xm, max(ytop, arrow_pts[:, 1].max() + 0.1)), extras=extras)


# ---------------------------------------------------------------- comprobacion contra workout.js (processNeckLateral)
def to_img(p, aspect):
    """coordenadas matematicas -> imagen normalizada (0..1) de un encuadre de ancho/alto = aspect; el muñeco ocupa ~80 % del alto"""
    s = 0.8 / (allp[:, 1].max() - allp[:, 1].min())
    return np.array([0.5 + p[0] * s / aspect, 0.9 - (p[1] - allp[:, 1].min()) * s])


def nose_and_shoulders(J, aspect):
    """nariz ~ centro de la cabeza un poco hacia la barbilla (la figura no la dibuja), hombros = los de build_front"""
    v = (J['hd'] - J['S']) / (np.linalg.norm(J['hd'] - J['S']) + 1e-9)
    nose = J['hd'] + v * 0.035 - v * 0.06
    return to_img(nose, aspect), to_img(J['R_arm'][0], aspect), to_img(J['L_arm'][0], aspect)


def metrics(J, aspect):
    n, r, l = nose_and_shoulders(J, aspect)
    mid = (r + l) / 2; sw = np.hypot(*(r - l))
    return (n[0] - mid[0]) / sw, (n[1] - mid[1]) / sw, mid                     # desviacion horizontal y vertical (en anchos de hombro), punto medio de hombros


for asp in (16 / 9, 4 / 3, 9 / 16):                                            # camara horizontal, 4:3 y vertical (movil)
    off0, vert0, mid0 = metrics(JF[0], asp)
    sw0 = np.hypot(*(nose_and_shoulders(JF[0], asp)[1] - nose_and_shoulders(JF[0], asp)[2]))
    assert abs(off0) < MIN_ENTER, f'centro (aspecto {asp:.2f}): debe contar como centrado para armar el contador'
    for i, k in enumerate(SEQ):
        off, vert, mid = metrics(JF[i], asp); off -= off0; vert -= vert0         # el contador descuenta su baseline (centro)
        drift = np.hypot(*(mid - mid0)) / sw0
        assert drift < 1e-6 and drift < DRIFT_TOL, f'{k}: los hombros no se mueven (drift {drift:.3f})'
        if k == 'C':
            assert abs(off) < EXIT, f'centro (aspecto {asp:.2f}): vuelve al centro (< {EXIT})'
        else:
            assert abs(off) > MIN_ENTER and abs(vert) < MAX_VERTICAL, f'{k} (aspecto {asp:.2f}): lado valido off={off:.2f} vert={vert:.2f}'
            assert (off > 0) == (k == 'R'), f'{k}: lado correcto'
            if asp == 16 / 9:
                print(f"inclinado {k} | desviacion nariz {abs(off):.2f} (> {MIN_ENTER}) | caida vertical {abs(vert):.2f} (< {MAX_VERTICAL}) | hombros quietos (deriva {drift:.2f} < {DRIFT_TOL})")
# pies apoyados y el torso, los hombros y los brazos identicos en todos los fotogramas (solo se mueven cuello y cabeza)
for J in JF[1:]:
    for sd in 'RL':
        assert abs(J[sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, 'los pies tocan el suelo'
        assert all(np.allclose(J[sd + '_arm'][j], JF[0][sd + '_arm'][j]) for j in range(3)), 'brazos y hombros no se mueven'
    assert np.allclose(J['S'], JF[0]['S']) and np.allclose(J['H'], JF[0]['H']), 'el torso no se mueve'
print('OK: la movilidad lateral de cuello coincide con los umbrales del contador (necklateral: processNeckLateral)')
