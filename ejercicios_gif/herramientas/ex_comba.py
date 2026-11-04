"""Comba (saltar a la cuerda), salto basico a dos pies, vista de PERFIL, mirando a la DERECHA como el resto de GIFs de ejercicios_gif (figura.py).
Mismo muñeco, suelo y flechas grises que tuck-jumps / burpees / sentadillas-con-salto. SIN cara (ni nariz ni ojo ni oreja): cabeza ovalada lisa (plain_head=True).

Forma de referencia (Elevate Rope «jump rope basics» y guias de salto basico): cuerpo erguido y alineado, hombros relajados, codos pegados a los costados,
manos a la altura de la cintura un poco por delante de la cadera, la cuerda la gira la muñeca (no el brazo), saltitos de 2-4 cm «justo para que pase la cuerda»
con los dos pies juntos, aterrizando sobre la parte delantera del pie (el talon casi no toca), rodillas ligeramente flexionadas, sin bloquearlas.
La cuerda se dibuja como un lazo que gira hacia delante (por encima de la cabeza -> delante -> bajo los pies -> detras -> otra vez arriba), con un mango en cada mano;
pasa POR DEBAJO de los pies justo en el fotograma en el aire.

Como lo mira la app (workout.js: counter "jumprope", processJumpRope, JUMPROPE_*; migracion 0118): cuenta el REBOTE vertical del cuerpo (media de la altura de hombros,
caderas y tobillos / largo del tronco), un pico por salto; descarta saltos grandes (JUMPROPE_MAX_SWING), brazos por encima del hombro (jumping jacks) y rodillas muy
subidas (correr en el sitio / tuck jumps). Vale de frente o de perfil. Las comprobaciones del final (assert) usan esos mismos umbrales.

GIF de 6 fotogramas (en bucle): cuerda arriba (listo) -> cuerda delante bajando -> impulso (puntas, cuerpo estirado, flecha arriba) ->
EN EL AIRE (pies despegados, la cuerda pasa por debajo) -> aterrizaje amortiguado (flecha abajo) -> cuerda detras subiendo -> vuelve al 1.
Uso: python ex_comba.py [carpeta_salida] [clave=valor ...]   (genera comba.gif + PNG de cada fotograma; usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *
from figura import _cap

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(hop=0.17,                         # cuanto se despegan los pies en el aire (unidades = troncos; ~0.06 seria el salto real de 2-4 cm, se exagera para verse)
           kS=166, kP=176, kA=173, kL=152,   # angulo de la rodilla: listo / impulso / aire / aterrizaje (nunca bloqueada del todo)
           footS=-14, footP=-42, footA=-52, footL=-20,   # inclinacion del pie (negativo = talon arriba, apoyado en la parte delantera)
           headd=5, far_dx=-0.08, arrows=1, margin=0.18, rx=1.25, ropew=1.3, bulge=0.13,
           durA=650, durB=450, durC=450, durD=800, durE=450, durF=450)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (JUMPROPE_*)
JUMPROPE_DELTA_MIN = 0.035          # subida+bajada minima del rebote (largos de tronco) para contar un pico
JUMPROPE_MAX_SWING = 0.55           # mas que esto no es un saltito de comba
JUMPROPE_ARMS_UP_MARGIN = 0.15      # muñeca por encima de (hombro + esto x tronco) = brazos arriba (jumping jacks)
JUMPROPE_KNEE_LIFT_MIN_RATIO = 0.55 # distancia vertical cadera->rodilla / la de pie por debajo de esto = rodilla subida

PLAIN = dict(plain_head=True)


def foot_ay(ang):
    """altura del tobillo para que la suela (parte mas baja del pie con esa inclinacion) quede en y=0 (igual que AY=0.14 con el pie plano)"""
    d = dv(ang); p = rot(d, -90); he = p * 0.10 - d * 0.07; to = he + d * 0.44
    return float(-foot_poly(np.zeros(2), he, to)[:, 1].min()) + 0.04


def hip_of(K, lean, ay):
    A = np.array([0.0, ay])
    knee = A + L_SHIN * np.array([np.sin(np.deg2rad(lean)), np.cos(np.deg2rad(lean))])
    return knee + L_THIGH * dv(270 - lean - K)


def pose(K, lean, t, foot, lift, ua, fa):
    ay = foot_ay(foot) + lift
    hip = hip_of(K, lean, ay)
    return dict(f=1, ground=False, hip=tuple(hip), torso=t, head=t + CFG['headd'], **PLAIN,
                near_leg=('ik', (0.0, ay), 'ccw', foot), far_leg=('ik', (CFG['far_dx'], ay), 'ccw', foot),
                near_arm=('fk', ua, fa), far_arm=('fk', ua - 5, fa - 4), near_hand=fa, far_hand=fa - 4)


# (rodilla, inclinacion de la espinilla, tronco, pie, despegue, brazo, antebrazo): codos pegados (brazo casi vertical), antebrazo adelante y un poco abajo, manos a la cintura
FRAMES = [
    pose(CFG['kS'], 3, 90, CFG['footS'], 0.0, 267, -20),                 # 1 listo: cuerda arriba
    pose(CFG['kS'] - 2, 3, 90, CFG['footS'], 0.0, 267, -12),             # 2 cuerda delante, baja hacia los pies
    pose(CFG['kP'], 1, 90, CFG['footP'], 0.0, 268, -10),                 # 3 impulso: puntas, cuerpo estirado
    pose(CFG['kA'], 0, 90, CFG['footA'], CFG['hop'], 268, -6),           # 4 EN EL AIRE: la cuerda pasa por debajo
    pose(CFG['kL'], 8, 86, CFG['footL'], 0.0, 266, -16),                 # 5 aterrizaje amortiguado
    pose(CFG['kS'] - 1, 3, 89, CFG['footS'], 0.0, 267, -22),             # 6 cuerda detras, subiendo
]
THETA = [110, 40, -45, -90, -145, 170]            # posicion del lazo de la cuerda (grados, 0 = delante, 90 = arriba; la cuerda gira hacia delante: el angulo baja)
NF = len(FRAMES)

# -------------------------------------------------- lazo de la cuerda: elipse centrada en el cuerpo, de la cabeza (+margen) hasta el suelo bajo los pies
J0 = build_side(FRAMES[0])
CX = 0.05
TOP = J0['hd'][1] + 0.33 + 0.28
BOT = -0.03
CY, RY = (TOP + BOT) / 2, (TOP - BOT) / 2
RX = CFG['rx']
ROPE_W = CFG['ropew']


def handle_pts(J, sd):
    wr = J[sd + '_arm'][2]; tip = J[sd + '_handtip']; d = (tip - wr) / (np.linalg.norm(tip - wr) + 1e-9)
    return tip - d * 0.10, tip + d * 0.17        # (dentro del puño, extremo del mango de donde sale la cuerda)


def strand(q, theta, k=1.0, bulge=0.0, n=48):
    """cuerda desde el extremo del mango q hasta el vertice del lazo (elipse), en espiral hacia fuera (arco convexo); bulge separa las dos hebras (lazo cerrado)"""
    u = (q[0] - CX) / RX; v = (q[1] - CY) / RY
    th_h = np.degrees(np.arctan2(v, u)); r_h = float(np.hypot(u, v))
    s = np.linspace(0, 1, n)
    th = np.radians(th_h + (theta - th_h) * s)
    r = r_h + (k - r_h) * (1 - (1 - s) ** 2)
    pts = np.stack([CX + r * RX * np.cos(th), CY + r * RY * np.sin(th)], 1)
    if bulge:
        t = np.gradient(pts, axis=0); t /= (np.linalg.norm(t, axis=1, keepdims=True) + 1e-9)
        pts = pts + np.stack([-t[:, 1], t[:, 0]], 1) * (bulge * np.sin(np.pi * s))[:, None]
    return pts


_state = dict(i=0)
_orig_draw_side = figura.draw_side


def draw_side_rope(pen, J, props_back=None):
    i = _state['i'] % NF; _state['i'] += 1
    th = THETA[i]; w = pen.c.LI * ROPE_W
    behind = np.cos(np.radians(th)) < -0.2           # cuerda por detras del cuerpo: las dos hebras quedan tapadas por el
    qn = handle_pts(J, 'near')[1]; qf = handle_pts(J, 'far')[1]
    # hebra lejana + mango lejano (detras del cuerpo)
    pen.line(strand(qf, th, 1.0, -CFG['bulge']), w=w)
    if behind:
        pen.line(strand(qn, th, 1.0, CFG['bulge']), w=w)
    p0, p1 = handle_pts(J, 'far'); _cap(pen, p0, p1, 0.075)
    _orig_draw_side(pen, J)
    # hebra cercana + mango cercano (delante del cuerpo)
    if not behind:
        pen.line(strand(qn, th, 1.0, CFG['bulge']), w=w)
    p0, p1 = handle_pts(J, 'near'); _cap(pen, p0, p1, 0.075)


figura.draw_side = draw_side_rope


def tang(th):
    """sentido de giro de la cuerda (hacia delante: el angulo baja) en el vertice del lazo"""
    t = np.radians(th); v = np.array([RX * np.sin(t), -RY * np.cos(t)]); return v / np.linalg.norm(v)


def flechas(i):
    if not CFG['arrows']:
        return None
    th = THETA[i]
    if i in (0, 1):      # la cuerda gira hacia delante (flecha gris al lado del vertice del lazo, en su sentido de giro)
        A = np.array([CX + RX * np.cos(np.radians(th)), CY + RY * np.sin(np.radians(th))])
        out = np.array([np.cos(np.radians(th)) / RX, np.sin(np.radians(th)) / RY]); out /= np.linalg.norm(out)
        a0 = A + out * 0.30 - tang(th) * 0.28
        return [lambda pen, a0=a0, t=tang(th): draw_line_arrow(pen, a0, a0 + t * 0.55)]
    x = CX + RX + 0.35
    if i == 2:           # impulso hacia arriba
        return [lambda pen: draw_line_arrow(pen, (x, 1.20), (x, 1.20 + 0.55))]
    if i == 4:           # amortigua hacia abajo
        return [lambda pen: draw_line_arrow(pen, (x, 2.10), (x, 2.10 - 0.55))]
    return None


durs = [int(CFG[k]) for k in ('durA', 'durB', 'durC', 'durD', 'durE', 'durF')]
render_scene(FRAMES, OUT + 'comba', durations=durs, margin=CFG['margin'], extras=[flechas(i) for i in range(NF)],
             bbox_extra=(CX - RX - 0.05, BOT - 0.05, CX + RX + 0.65, TOP + 0.40))

# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (processJumpRope)
Js = [build_side(fr) for fr in FRAMES]
names = ('listo', 'cuerda delante', 'impulso', 'en el aire', 'aterrizaje', 'cuerda detras')
J0 = Js[0]
torso0 = J0['S'][1] - J0['H'][1]
thigh0 = J0['H'][1] - J0['near_leg'][1][1]


def foot_low(J, sd):
    hp, kn, an, he, to = J[sd + '_leg']
    return float(foot_poly(an, he, to)[:, 1].min())


hs, ground_low = [], []
for i, (nm, J) in enumerate(zip(names, Js)):
    S, H = J['S'], J['H']
    ankles = [J[s + '_leg'][2][1] for s in ('near', 'far')]
    h = (S[1] * 2 + H[1] * 2 + sum(ankles)) / 6 / torso0                    # media de hombros, caderas y tobillos / tronco (la señal "h" de la app)
    hs.append(h)
    lows = [foot_low(J, s) for s in ('near', 'far')]
    ground_low.append(min(lows))
    kr = min((H[1] - J[s + '_leg'][1][1]) / thigh0 for s in ('near', 'far'))
    wr_y = max(J[s + '_arm'][2][1] for s in ('near', 'far'))
    assert kr >= JUMPROPE_KNEE_LIFT_MIN_RATIO + 0.2, f'{nm}: rodilla subida ({kr:.2f}) -> la app lo descartaria como correr en el sitio'
    assert wr_y < S[1] - JUMPROPE_ARMS_UP_MARGIN * torso0, f'{nm}: las manos no deben pasar del hombro (jumping jacks)'
    assert wr_y < H[1] + 0.8 * torso0, f'{nm}: manos a la cintura'
    print(f'{nm:15s}| h {h:.3f} | rodilla/muslo {kr:.2f} (mín {JUMPROPE_KNEE_LIFT_MIN_RATIO}) | muñeca {(wr_y - H[1]) / torso0:+.2f} troncos sobre la cadera | pie a {ground_low[-1] - 0.04:+.3f} del suelo')

for i in (0, 1, 2, 4, 5):
    assert abs(ground_low[i] - 0.04) < 6e-3, f'{names[i]}: los pies deben quedar apoyados en el suelo ({ground_low[i]:.3f})'
assert ground_low[3] - 0.04 > 0.12, 'en el aire los pies deben verse despegados'
swing = max(hs) - min(hs)
print(f'rebote del cuerpo en un ciclo: {swing:.3f} troncos (mín {JUMPROPE_DELTA_MIN}, máx {JUMPROPE_MAX_SWING})')
assert swing >= 2 * JUMPROPE_DELTA_MIN, 'el rebote debe superar con holgura el delta minimo de la app'
assert swing <= JUMPROPE_MAX_SWING, 'demasiado salto: la app lo descartaria (JUMPROPE_MAX_SWING)'
# detector de picos con histeresis (como processJumpRope: sube y baja al menos "delta"), sobre 3 ciclos seguidos; se cuentan los picos del ciclo central
delta = 2 * JUMPROPE_DELTA_MIN
seq = hs * 3; look_max, mx, mx_i, mn, peaks_i = True, seq[0], 0, seq[0], []
for j, v in enumerate(seq):
    if look_max:
        if v > mx: mx, mx_i = v, j
        if v < mx - delta: peaks_i.append(mx_i); look_max, mn = False, v
    else:
        if v < mn: mn = v
        if v > mn + delta: look_max, mx, mx_i = True, v, j
peaks = sum(1 for j in peaks_i if NF <= j < 2 * NF)
assert peaks == 1 and max(range(NF), key=lambda j: hs[j]) == 3, 'un ciclo del GIF debe tener un solo pico de rebote (en el aire) = 1 salto'
print('picos de rebote por ciclo:', peaks, '=> 1 salto = 1 repeticion')
print('OK: la comba coincide con los umbrales del contador (jumprope, processJumpRope)')
