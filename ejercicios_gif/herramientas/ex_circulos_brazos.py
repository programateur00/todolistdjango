"""Círculos de brazos (arm circles), DE FRENTE. Mismo muñeco, suelo y flechas grises que el resto de GIFs de ejercicios_gif (figura.py).
SIN cara (sin nariz, ojo ni oreja: draw_front solo dibuja un ovalo liso).

Forma (guias de arm circles: Sweat, Pfizer HealthAnswers, Trainwell): de pie, pies a la anchura de la cadera, los DOS brazos ESTIRADOS a los lados
a la altura de los hombros (en T), y se giran los dos a la vez haciendo circulos desde el hombro, sin doblar los codos. Se hacen en un sentido y
luego en el otro.

Es DE FRENTE y con el circulo en el plano de la imagen a proposito: es lo que mide el contador de la app (counter_key="armcircles",
processArmCircles en workout.js, migracion 0033, mode pose). Para cada brazo calcula el ANGULO de la muñeca alrededor de su propio hombro en la
imagen (X normalizado para que "hacia fuera" sea + en los dos lados, Y invertido para que "arriba" sea +), lo acumula frame a frame y una vuelta
completa (|acumulado| >= 2*pi) = 1 repeticion. "Hacia delante" = angulo DECRECIENTE. Los dos brazos son simetricos (espejo), asi que giran con el
MISMO signo, como exige el contador.

Como se ve (v2, natural): los brazos NO se cruzan estirados por delante del pecho (eso era antinatural). Al pasar por la parte de DENTRO del circulo
los brazos van hacia la camara (se ven acortados por el escorzo) y las manos se encuentran en la LINEA CENTRAL, delante del cuerpo, y suben juntas
por ella (vientre -> pecho -> barbilla) hasta ponerse, ya estiradas, por encima de la cabeza; desde ahi se abren a los lados y bajan.
Fotogramas (por defecto 12, pasos de 30°): T (posicion de armado) -> abajo-fuera -> abajo -> manos al vientre -> pecho -> barbilla -> arriba
(paralelos, sobre la cabeza) -> arriba-fuera -> T. Una flecha gris curva por hombro en los fotogramas de fuera y una flecha recta central
mientras las manos suben juntas. Una vuelta del GIF = 1 repeticion hacia delante.
Uso: python ex_circulos_brazos.py [carpeta_salida] [clave=valor ...]   (genera arm-circles.gif + PNG de cada fotograma; usar una carpeta
temporal, no ejercicios_gif)
Parametros: steps (fotogramas por vuelta, defecto 12), back=1 (sentido contrario, "hacia atras"), arrows=0 (sin flechas), meet (cuanto se pasan las
manos de la linea central al encontrarse, 0.10 = cruce pequeño, 0 = se tocan justo en el centro), arr_r (radio de las flechas), bot (grados que se abren los brazos abajo para no solaparse con el
cuerpo), hip_y, margin, durT, durS.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(steps=12, back=0, arrows=1, arr_r=1.43, bot=6.0, hip_y=2.0, margin=0.30, durT=900, durS=250, meet=0.10)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)
N = int(CFG['steps']); BACK = bool(CFG['back'])

# mismos umbrales que workout.js (ARMCIRCLES_*)
MIN_VIS_REACH = 0.45        # ARMCIRCLES_MIN_REACH_FACTOR: muñeca a >= 0.45 anchos de hombro del hombro (brazo extendido)
MAX_HANG_REL = 0.35         # ARMCIRCLES_MAX_HANG_REL: al armar, muñeca como mucho 0.35 anchos de hombro POR DEBAJO del hombro
MIN_ANGULAR_DELTA = 0.09    # ARMCIRCLES_MIN_ANGULAR_DELTA (rad/frame)
MAX_SINGLE_ARM_DELTA = 3.0  # ARMCIRCLES_MAX_SINGLE_ARM_DELTA (rad)
ARM_DISAGREE_RAD = 1.0      # ARMCIRCLES_ARM_DISAGREE_RAD
MIN_REP_SECONDS = 0.35      # ARMCIRCLES_MIN_REP_SECONDS

STAND = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268))
mirror = lambda t: 180 - t


def theta_of(i):
    """angulo LOCAL de cada brazo (0 = a un lado, +90 = arriba, -90 = abajo) en el fotograma i; 'hacia delante' = decreciente"""
    t = -360.0 * i / N * (-1 if BACK else 1)
    return t


SW = 0.34                                                  # mitad del ancho de hombros (figura.build_front)
ARM = L_UA + L_FA


def fore(theta):
    """escorzo del brazo (1 = estirado en el plano de la imagen). Hacia DENTRO el brazo va hacia la camara y se acorta lo justo para que la
    muñeca no pase de la linea central del cuerpo (como mucho CFG['meet'] de mas): las manos se encuentran delante del pecho y no se cruzan"""
    c = np.cos(np.deg2rad(theta))
    if c >= -1e-9:
        return 1.0
    return min(1.0, (SW + CFG['meet']) / (-c) / ARM)


def pose(theta):
    t = theta
    # abajo del todo (-90) el brazo se abre unos grados para no quedar tapado por el torso/muslo (como DOWN de jumping-jacks)
    near_bottom = abs(((t + 90 + 180) % 360) - 180)
    if near_bottom < 1e-6:
        t = -90 + CFG['bot'] * 1.0
    f = fore(theta)
    return dict(view='front', hip=(0, CFG['hip_y']), torso=90, head=90, **STAND,
                R_arm=('fk', t, t), L_arm=('fk', mirror(t), mirror(t)),
                fore_R_ua=f, fore_R_fa=f, fore_L_ua=f, fore_L_fa=f)


THETAS = [theta_of(i) for i in range(N)]
FORE = [fore(t) for t in THETAS]
FRAMES = [pose(t) for t in THETAS]


def final_J(fr):
    J = build_front(fr)
    return shift_front(J, front_shift(J) + fr.get('dy', 0))


JF = [final_J(f) for f in FRAMES]


# ---------------------------------------------------------------- extras: flechas grises de giro alrededor de cada hombro
def flechas(i):
    if not CFG['arrows']:
        return None
    J = JF[i]; step = 360.0 / N * (1 if BACK else -1)         # cuanto avanza theta en un fotograma (negativo = hacia delante)
    t = THETAS[i]
    inward = FORE[i] < 0.97                                    # brazo acortado: las manos van por el centro

    def draw(pen):
        if inward:
            # flecha recta central en el sentido en que se mueven las manos (de este fotograma al siguiente)
            nxt = pose(t + step)
            Jn = final_J(nxt)
            w0 = (J['R_arm'][2] + J['L_arm'][2]) / 2; w1 = (Jn['R_arm'][2] + Jn['L_arm'][2]) / 2
            v = w1 - w0; v = v / (np.linalg.norm(v) + 1e-9)
            a_ = w0 + v * 0.16
            draw_line_arrow(pen, a_, a_ + v * 0.42)
            return
        R_ARR = FORE[i] * ARM + (CFG['arr_r'] - ARM)
        for sd in 'RL':
            sh = J[sd + '_arm'][0]
            a = t if sd == 'R' else mirror(t)
            s = step if sd == 'R' else -step
            # arco centrado en la posicion actual de la mano, un poco mas alla de la punta, avanzando en el sentido del giro; se corta antes de
            # llegar a la linea central del cuerpo para que las dos flechas no se junten en X
            angs = np.linspace(a - 0.3 * s, a + 0.62 * s, 90)
            ok = np.array([abs((sh + R_ARR * dv(aa))[0]) >= 0.16 for aa in angs])
            runs, cur = [], []
            for k_, f_ in enumerate(ok):                      # tramos seguidos del arco que quedan fuera de la zona central
                if f_: cur.append(k_)
                elif cur: runs.append(cur); cur = []
            if cur: runs.append(cur)
            if runs:
                r_ = max(runs, key=len)
                if abs(angs[r_[-1]] - angs[r_[0]]) >= 12:
                    draw_arrow(pen, sh, R_ARR, angs[r_[0]], angs[r_[-1]])
    return [draw]


allp = np.vstack([pts_front(J) for J in JF])
shR = max(J['R_arm'][0][1] for J in JF); xm = JF[0]['R_arm'][0][0] + CFG['arr_r'] + 0.05
ytop = shR + CFG['arr_r'] + 0.05
bb = (-xm, 0.0, xm, max(ytop, allp[:, 1].max())) if CFG['arrows'] else None
durs = [CFG['durT']] + [CFG['durS']] * (N - 1)
imgs = render_scene(FRAMES, OUT + 'arm-circles', durations=[int(x) for x in durs], margin=CFG['margin'],
                    bbox_extra=bb, extras=[flechas(i) for i in range(N)])


# ---------------------------------------------------------------- comprobacion contra workout.js (processArmCircles)
def to_img(p, aspect):
    """coordenadas matematicas -> imagen normalizada (0..1) de un encuadre de ancho/alto = aspect; el muñeco ocupa ~80 % del alto"""
    s = 0.8 / (allp[:, 1].max() - allp[:, 1].min())
    return np.array([0.5 + p[0] * s / aspect, 0.9 - (p[1] - allp[:, 1].min()) * s])


def wrap(d):
    while d > np.pi: d -= 2 * np.pi
    while d < -np.pi: d += 2 * np.pi
    return d


def landmarks(J, aspect):
    """el brazo derecho de la imagen (mi 'R') es el 'L_*' de MediaPipe (aparece a la derecha del frame sin espejar); el izquierdo, el 'R_*'"""
    g = lambda sd: dict(S=to_img(J[sd + '_arm'][0], aspect), W=to_img(J[sd + '_arm'][2], aspect))
    return g('R'), g('L')


def angles(J, aspect):
    l, r = landmarks(J, aspect)
    sw = np.hypot(*(l['S'] - r['S']))
    aL = np.arctan2(-(l['W'][1] - l['S'][1]), l['W'][0] - l['S'][0])
    aR = np.arctan2(-(r['W'][1] - r['S'][1]), -(r['W'][0] - r['S'][0]))
    reachL = np.hypot(*(l['W'] - l['S'])) / sw; reachR = np.hypot(*(r['W'] - r['S'])) / sw
    hangL = (l['W'][1] - l['S'][1]) / sw; hangR = (r['W'][1] - r['S'][1]) / sw     # y de imagen: abajo = mayor
    return aL, aR, reachL, reachR, hangL, hangR


def simulate(aspect, verbose=False):
    """un ciclo del GIF a traves de la maquina de estados de processArmCircles: devuelve (acumulado, repeticiones, direccion)"""
    A = [angles(J, aspect) for J in JF]
    aL0, aR0, rL0, rR0, hL0, hR0 = A[0]
    assert rL0 > MIN_VIS_REACH and rR0 > MIN_VIS_REACH, f'armado: brazos extendidos (reach {rL0:.2f}/{rR0:.2f} anchos de hombro, umbral {MIN_VIS_REACH})'
    assert hL0 < MAX_HANG_REL and hR0 < MAX_HANG_REL, f'armado: muñecas no colgando (hang {hL0:+.2f}/{hR0:+.2f}, umbral {MAX_HANG_REL})'
    accum = 0.0; prevL, prevR = aL0, aR0; deltas = []
    for k in range(1, N + 1):
        aL, aR, rL, rR, _, _ = A[k % N]
        assert rL > MIN_VIS_REACH and rR > MIN_VIS_REACH, f'fotograma {k % N}: los dos brazos extendidos (reach {rL:.2f}/{rR:.2f})'
        dl, dr = wrap(aL - prevL), wrap(aR - prevR)
        assert abs(dl) <= MAX_SINGLE_ARM_DELTA and abs(dr) <= MAX_SINGLE_ARM_DELTA, f'fotograma {k % N}: salto de angulo demasiado grande ({dl:.2f}, {dr:.2f})'
        assert not (dl * dr < 0 and abs(dl - dr) > ARM_DISAGREE_RAD), f'fotograma {k % N}: los dos brazos se contradicen ({dl:.2f}, {dr:.2f})'
        assert dl * dr > 0, f'fotograma {k % N}: los dos brazos giran en el mismo sentido ({dl:.2f}, {dr:.2f})'
        avg = (dl + dr) / 2
        assert abs(avg) >= MIN_ANGULAR_DELTA, f'fotograma {k % N}: avance angular {avg:.2f} rad < {MIN_ANGULAR_DELTA} (se tomaria por quietud)'
        accum += avg; prevL, prevR = aL, aR; deltas.append(np.rad2deg(avg))
    reps = int(abs(accum) >= 2 * np.pi - 1e-6)      # un ciclo exacto del GIF cierra los 360° (tolerancia de redondeo)
    if verbose:
        print(f"  aspecto {aspect:.2f}: avance por fotograma {min(abs(d) for d in deltas):.0f}°–{max(abs(d) for d in deltas):.0f}°, acumulado {np.rad2deg(accum):+.0f}°")
    return accum, reps, ('forward' if accum < 0 else 'backward')


for asp in (16 / 9, 4 / 3, 9 / 16):                                      # camara horizontal, 4:3 y vertical (movil)
    accum, reps, direction = simulate(asp, verbose=True)
    assert reps == 1, f'un ciclo del GIF debe contar exactamente 1 repeticion (acumulado {np.rad2deg(accum):.0f}°)'
    assert direction == ('backward' if BACK else 'forward'), f'sentido detectado {direction}'
# pies apoyados y brazos estirados (reach identico) en todos los fotogramas; el cuerpo no se mueve
for fi, J in enumerate(JF):
    for sd in 'RL':
        assert abs(J[sd + '_leg'][2][1] - JF[0]['R_leg'][2][1]) < 4e-3, 'los pies tocan el suelo'
        sh, e, w = J[sd + '_arm']
        v1, v2 = (e - sh), (w - e)
        assert abs(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2)) - 1) < 1e-6, 'brazo recto (sin doblar el codo)'
        assert abs(np.linalg.norm(w - sh) - FORE[fi] * (L_UA + L_FA)) < 1e-6
        assert w[0] * np.sign(sh[0]) >= -CFG['meet'] - 1e-6, f'las manos no se cruzan: la muñeca no pasa de la linea central (x={w[0]:.2f})'
assert all(np.allclose(J['S'], JF[0]['S']) and np.allclose(J['H'], JF[0]['H']) for J in JF), 'el torso no se mueve'
assert (CFG['durT'] + CFG['durS'] * (N - 1)) / 1000 >= MIN_REP_SECONDS, 'una vuelta del GIF dura mas que ARMCIRCLES_MIN_REP_SECONDS'
print('repeticiones contadas en un ciclo: 1,', 'hacia atras' if BACK else 'hacia delante')
print('OK: los circulos de brazos coinciden con los umbrales del contador (armcircles, processArmCircles)')
