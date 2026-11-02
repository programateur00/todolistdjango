"""Plancha lateral con golpe de cadera (hip dips), vista DE FRENTE (la camara ve la barriga), tumbado de lado con la cabeza a la DERECHA y los pies a la izquierda,
igual que side-plank.gif / hollow-body-hold.gif (mismo muñeco, estilo, suelo y flechas grises: figura.py). SIN cara (ni nariz ni ojo ni oreja:
figura.draw_front no dibuja cara y aqui NO se usa ninguna funcion cara()).
Genera UN GIF: side-plank-hip-dips.gif (slug side-plank-hip-dips, counter_key=sideplankhipdips, processSidePlankHipDips).
  plancha lateral con la cadera ALZADA (cuerpo recto; flecha gris hacia abajo) -> bajando -> la cadera baja CASI hasta el suelo (flecha gris hacia arriba) -> subiendo -> (bucle).
El hombro, el codo y el antebrazo de apoyo NO se mueven (el hombro no se hunde, como pide el ejercicio): el cuerpo se dobla un poco por la cadera y vuelve a la linea recta.
Como lo mira la app (workout.js), con los landmarks de MediaPipe en la imagen (y hacia ABAJO):
  - se ARMA con checkSidePlankPosture (SIDEPLANK_*): linea hombro-cadera-tobillo, inclinacion, cadera alzada, codo bajo el hombro, antebrazo apoyado (= la plancha lateral normal, fotograma 1),
  - h = (altura media de codo y tobillo de abajo [= suelo] - altura de la cadera) / largo hombro-tobillo (con la x a escala 16:9, landscapeLm); referencia "arriba" = h al armar,
  - baja cuando bajada = ref - h >= max(HIPDIP_DOWN_FRACTION * ref, HIPDIP_MIN_DROP) y SE CUENTA al volver a bajada <= HIPDIP_UP_FRACTION * ref,
  - se corta si la inclinacion hombro->cadera supera HIPDIP_BROKEN_TILT_DEG (te has puesto de pie).
Al final se comprueban los umbrales y se simula la maquina de estados sobre el ciclo (assert).
Uso: python ex_side_plank_hip_dips.py [carpeta_salida] [clave=valor ...]   (genera side-plank-hip-dips.gif + PNG de cada fotograma: usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(sw=0.34,                               # semi-ancho de hombros (figura.build_front: shoulder_w)
           e_y=0.10,                              # altura del codo / mano de apoyo sobre el suelo (radio del brazo ~0.095)
           fa=0.42, fa_dir=180,                   # antebrazo de apoyo: fraccion de su largo (esta de frente, en escorzo) y direccion (180 = hacia los pies)
           arm_up=1, up_dx=-0.02, up_dy=0.30,     # mano de arriba: 1 = estirada al techo (como side-plank.gif), 0 = sobre la cadera; up_dx/up_dy: posicion de la mano sobre la cadera
           dip_gap=0.045,                         # hueco entre el pantalon y el suelo cuando la cadera esta abajo ("casi hasta el suelo")
           mid=0.5,                               # fraccion del recorrido de los fotogramas intermedios (0 = arriba, 1 = abajo)
           head_dt=0, margin=0.30, arrows=1, arr_len=0.40, arr_dx=0.05, arr_y=0.62,
           stack=0.17, dur_up=900, dur_mid=450, dur_dn=900)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js
SIDEPLANK_LINE_MIN_DEG = 145
SIDEPLANK_MAX_TILT_DEG = 45
SIDEPLANK_MIN_HIP_LIFT = 0.22
SIDEPLANK_MAX_HIP_LIFT = 1.2
SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN = 0.22
PLANK_ARMS_DOWN_MARGIN = 0.3
MIN_BODY_LENGTH_FACTOR = 1.8        # largo hombro-tobillo / ancho de hombros
HIPDIP_MIN_UP_REF = 0.05
HIPDIP_DOWN_FRACTION = 0.4
HIPDIP_UP_FRACTION = 0.25
HIPDIP_MIN_DROP = 0.03
HIPDIP_REF_ALPHA = 0.1
HIPDIP_BROKEN_TILT_DEG = 60
LYING_REF_ASPECT = 16 / 9

SW = CFG['sw']
HW = 0.15                           # semi-ancho de caderas (figura.build_front)
LEG = L_THIGH + L_SHIN
FOOT_DROP, FOOT_SIDE, FOOT_RY = 0.10, 0.03, 0.08   # zapatilla de figura.draw_front: centro = tobillo - ud*0.10 + n*fd*0.03, semieje vertical 0.08


def nvec(t):                        # figura.build_front: n = dv(t - 90)
    return dv(t - 90)


def foot_bottom(an, t, fd):
    n = nvec(t); ud = dv(t)
    return float((an - ud * FOOT_DROP + n * fd * FOOT_SIDE)[1] - FOOT_RY)


def bisect(f, lo, hi, it=60):
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (flo > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def hull_bottom(J):
    """punto mas bajo de la cadera (el pantalon corto de figura.draw_front): 2 puntos del cinturon + redondeo de cada muslo"""
    S, H, n = J['S'], J['H'], J['n']
    ys = [(S + (H - S) * s2 + n * sg * wd)[1] for sg in (1, -1) for s2, wd in ((0.80, 0.27), (1.0, 0.31))]
    for sd in 'RL':
        hp = J[sd + '_leg'][0]; ys.append(hp[1] - 0.21)
    return min(ys)


# ---------------------------------------------------------------- plancha lateral (cadera alzada, cuerpo recto): igual que side-plank.gif
def solve_plank():
    def feet_gap(t):                 # suelo: codo (e_y) y pie de abajo a la vez
        n = nvec(t)
        Sy = CFG['e_y'] + L_UA + SW * np.cos(np.deg2rad(t))          # hombro de abajo = codo + brazo vertical
        Hy = Sy - np.sin(np.deg2rad(t))
        hp = np.array([0, Hy]) + n * HW
        an = hp + dv(t + 180) * LEG
        return foot_bottom(an, t, +1)
    t = bisect(feet_gap, 4.0, 35.0)
    return t


tB = solve_plank()
SH_Y = CFG['e_y'] + L_UA                                           # altura del hombro de abajo (fija en todo el ejercicio)
SH_X = np.cos(np.deg2rad(tB)) + SW * np.sin(np.deg2rad(tB))        # x del hombro de abajo (fija: la cadera sale de aqui con H.x = 0 en la plancha)


def hip_for(t):
    """cadera para un angulo de torso t con el hombro de abajo FIJO en (SH_X, SH_Y): H = S - dv(t), S = hombro + n*SW"""
    n = nvec(t)
    S = np.array([SH_X, SH_Y]) - n * SW           # centro de hombros (hombro R = S + n*SW)
    return S - dv(t)


def pose(t):
    """t = angulo del torso (hombro-cadera sobre la horizontal). tB = plancha recta; mayor = cadera mas abajo"""
    H = hip_for(t); n = nvec(t)
    hp = H + n * HW
    if abs(t - tB) < 1e-9:           # plancha: pierna de abajo recta en la linea del cuerpo
        phi = t + 180
    else:                            # cadera hundida: el cuerpo se dobla por la cadera y el pie de abajo sigue en el suelo
        phi = bisect(lambda ph: foot_bottom(hp + dv(ph) * LEG, t, +1), 170.0, 200.0)
    an = hp + dv(phi) * LEG
    p = dict(view='front', ground=False, hip=tuple(H), torso=t, head=t + CFG['head_dt'], shoulder_w=SW,
             R_arm=('fk', 270, CFG['fa_dir']), fore_R_fa=CFG['fa'], fore_R_ua=1.0,
             R_leg=('fk', phi, phi, +1), L_leg=('ik', an + np.array([0, CFG['stack']]), 'cw', +1))
    if CFG['arm_up']:
        p['L_arm'] = ('fk', 90, 90)
    else:   # mano de arriba sobre la cadera de arriba (codo hacia arriba)
        tgt = H - n * (HW + CFG['up_dy']) + dv(t + 180) * (-CFG['up_dx'])
        p['L_arm'] = ('ik', tgt, 'cw')
    return p


def solve_dip():
    f = lambda t: hull_bottom(build_front(pose(t))) - CFG['dip_gap']
    return bisect(f, tB + 0.5, 75.0)


tD = solve_dip()
tM = tB + CFG['mid'] * (tD - tB)
PB, PM, PD = pose(tB), pose(tM), pose(tD)
JB, JM, JD = build_front(PB), build_front(PM), build_front(PD)


# ---------------------------------------------------------------- extras: flechas grises (junto a la cadera: abajo en la plancha, arriba con la cadera abajo)
def flecha(J, down):
    def f(pen):
        if not CFG['arrows']:
            return
        x = JB['H'][0] + CFG['arr_dx']
        y0 = J['H'][1] + CFG['arr_y']                  # justo encima de la cadera de ESTE fotograma
        a = (x, y0 + CFG['arr_len']) if down else (x, y0)
        b = (x, y0) if down else (x, y0 + CFG['arr_len'])
        draw_line_arrow(pen, a, b)
    return f


allp = np.vstack([pts_front(JB), pts_front(JM), pts_front(JD)])
bb = (allp[:, 0].min() - 0.1, 0.0, allp[:, 0].max() + 0.1, allp[:, 1].max() + 0.1)
render_scene([PB, PM, PD, PM], OUT + 'side-plank-hip-dips',
             durations=[int(CFG['dur_up']), int(CFG['dur_mid']), int(CFG['dur_dn']), int(CFG['dur_mid'])], margin=CFG['margin'],
             bbox_extra=bb, extras=[[flecha(JB, True)], [], [flecha(JD, False)], []])


# ---------------------------------------------------------------- comprobacion contra workout.js
def img(p):                          # coordenadas de imagen (y hacia abajo), como MediaPipe
    return np.array([p[0], -p[1]], float)


def angd(a, b, c):
    return float(np.degrees(np.arccos(np.clip(np.dot(a - b, c - b) / (np.linalg.norm(a - b) * np.linalg.norm(c - b)), -1, 1))))


def measures(J, aspect_k=1.0):
    """medidas de la app. aspect_k = factor x de landscapeLm sobre una x isotropica (1 = isotropico; 9/16 = x como en un video 16:9 normalizado)"""
    sc = np.array([aspect_k, 1.0])
    sh = {s: img(J[s + '_arm'][0]) * sc for s in 'RL'}
    sw = float(np.linalg.norm(sh['R'] - sh['L']))
    down = 'R' if sh['R'][1] > sh['L'][1] else 'L'
    S_, E_, W_ = (img(x) * sc for x in J[down + '_arm'])
    hp, kn, an = (img(x) * sc for x in J[down + '_leg'][:3])
    ground = (E_[1] + an[1]) / 2
    body = float(np.linalg.norm(S_ - an))
    return dict(down=down, line=angd(S_, hp, an), tilt=float(np.degrees(np.arctan2(abs(hp[1] - S_[1]), abs(hp[0] - S_[0])))),
                hipLift=(ground - hp[1]) / sw, elbowDrop=(E_[1] - S_[1]) / sw, armDown=(W_[1] - S_[1]) / sw,
                bodyLen=body / sw, elbowX=E_[0] - S_[0], h=(ground - hp[1]) / body, an=an, sh=S_)


def tilt_raw(J, aspect):
    """tiltFromHorizontal con los landmarks normalizados de un video width/height = aspect (x_norm = X / aspect)"""
    return measures(J, 1.0 / aspect)['tilt']


mB, mM, mD = measures(JB), measures(JM), measures(JD)
for nm, m in (('plancha (arriba)', mB), ('intermedio', mM), ('cadera abajo', mD)):
    print(f"{nm:18s} lado abajo={m['down']} linea {m['line']:.0f}° tilt {m['tilt']:.0f}° hipLift {m['hipLift']:.2f} elbowDrop {m['elbowDrop']:.2f} armDown {m['armDown']:.2f}")
# 1) fotograma 1 = plancha lateral normal: pasa checkSidePlankPosture con margen
assert mB['down'] == mM['down'] == mD['down'] == 'R', 'el lado de abajo (hombro mas bajo) es el que apoya en todos los fotogramas'
assert mB['line'] >= SIDEPLANK_LINE_MIN_DEG + 15, 'plancha: cuerpo en linea recta (con margen)'
assert mB['tilt'] <= SIDEPLANK_MAX_TILT_DEG * 0.6, 'tumbado de lado, no de pie'
assert SIDEPLANK_MIN_HIP_LIFT * 1.5 <= mB['hipLift'] <= SIDEPLANK_MAX_HIP_LIFT * 0.8, 'cadera alzada con margen y sin pasarse'
assert mB['elbowDrop'] >= SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN * 2 and abs(mB['elbowX']) < 0.1, 'codo bien por debajo del hombro y justo debajo'
assert mB['armDown'] >= PLANK_ARMS_DOWN_MARGIN * 2, 'antebrazo de abajo apoyado'
assert mB['bodyLen'] >= MIN_BODY_LENGTH_FACTOR, 'cuerpo entero extendido'
# 2) hombro, codo y muñeca de apoyo no se mueven (el hombro no se hunde)
for J in (JM, JD):
    for i in range(3):
        assert np.allclose(J['R_arm'][i], JB['R_arm'][i], atol=1e-6), 'brazo de apoyo quieto'
# 3) contador: h (con la x a escala 16:9) y maquina de estados
K169 = 1.0 / LYING_REF_ASPECT * 1.0            # x_norm(16:9) = X / (16/9 * alto): misma escala que landscapeLm de un video de cualquier aspecto
hB, hM, hD = (measures(J, K169)['h'] for J in (JB, JM, JD))
ref = max(hB, HIPDIP_MIN_UP_REF)
dropM, dropD = ref - hM, ref - hD
print(f"h (16:9) arriba {hB:.3f}  intermedio {hM:.3f}  abajo {hD:.3f}  | bajada intermedio {dropM / ref * 100:.0f}% y abajo {dropD / ref * 100:.0f}% de la referencia (baja >= {HIPDIP_DOWN_FRACTION * 100:.0f}%, sube <= {HIPDIP_UP_FRACTION * 100:.0f}%)")
assert dropD >= max(HIPDIP_DOWN_FRACTION * ref, HIPDIP_MIN_DROP) * 1.5, 'cadera abajo: baja con margen'
assert hD > -0.02, 'cadera abajo: casi apoyada, sin atravesar el suelo'
# inclinacion: de frente, hombro->cadera sobre la horizontal. Con la x en 16:9 (el peor caso) sigue < HIPDIP_BROKEN_TILT_DEG
for nm, asp in (('16:9', 16 / 9), ('4:3', 4 / 3), ('1:1', 1.0)):
    tl = tilt_raw(JD, asp)
    print(f"inclinacion hombro-cadera con la cadera abajo, video {nm}: {tl:.0f}°")
    assert tl < HIPDIP_BROKEN_TILT_DEG * 0.9, f'cadera abajo: inclinacion < HIPDIP_BROKEN_TILT_DEG en video {nm}'
    assert tilt_raw(JB, asp) <= SIDEPLANK_MAX_TILT_DEG, f'plancha: inclinacion <= SIDEPLANK_MAX_TILT_DEG en video {nm}'


def sim(hs):
    """replica de processSidePlankHipDips (estado 'up'/'down' tras armar con hs[0]); devuelve repeticiones"""
    r = max(hs[0], HIPDIP_MIN_UP_REF); st = 'up'; reps = 0
    for h in hs[1:]:
        drop = r - h
        if st == 'up':
            if drop >= max(HIPDIP_DOWN_FRACTION * r, HIPDIP_MIN_DROP):
                st = 'down'
            elif drop < HIPDIP_UP_FRACTION * r:
                r = max(HIPDIP_MIN_UP_REF, r + HIPDIP_REF_ALPHA * (h - r))
        elif drop <= HIPDIP_UP_FRACTION * r:
            reps += 1; st = 'up'
    return reps


def cycle_h(n=24, cycles=3, k=None):
    k = K169 if k is None else k
    hs = []
    for c in range(cycles):
        for i in range(n):
            s = 0.5 - 0.5 * np.cos(2 * np.pi * i / n)       # 0 -> 1 -> 0 suave
            hs.append(measures(build_front(pose(tB + s * (tD - tB))), k)['h'])
    hs.append(measures(JB, k)['h'])
    return hs


reps = sim(cycle_h())      # landscapeLm lleva la x de cualquier aspecto (16:9, 4:3, 1:1) a la misma escala 16:9: el contador ve siempre lo mismo
assert reps == 3, f'3 vueltas = 3 repeticiones ({reps})'
print('simulada la maquina de estados: 3 ciclos = 3 repeticiones, exactamente 1 por vuelta')
print(f"torso: plancha {tB:.1f}°, intermedio {tM:.1f}°, cadera abajo {tD:.1f}°")
print('OK: la plancha lateral con golpe de cadera coincide con los umbrales del contador (sideplankhipdips, processSidePlankHipDips)')
