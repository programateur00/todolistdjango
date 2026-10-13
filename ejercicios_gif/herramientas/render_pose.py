"""Dos poses fijas (inicio / esfuerzo) en estilo line-art tipo Everkinetic.
Uso: render5.py pose30.npz salida_base [--lift 0.7]
Genera: <base>_1.png, <base>_2.png, <base>.gif (2 fotogramas), <base>_par.png (las dos juntas)
"""
import sys, os, numpy as np, cv2
from PIL import Image

npz, BASE = sys.argv[1], sys.argv[2]
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
TARGET_LIFT = float(arg("--lift", 0.7))
CW, CH, SS = 480, 360, 3
INK, WHITE, SHORTS, FLOOR = (24, 24, 24), (255, 255, 255), (238, 238, 238), (200, 200, 200)

# ====================================================================== datos
d = np.load(npz)
lm, t, W, H, FPS = d["lm"].copy(), d["t"], int(d["W"]), int(d["H"]), float(d["fps"])
N = len(t)
px = lm[:, :, :2] * np.array([W, H], np.float32)
zz = lm[:, :, 2] * W
vis = np.nan_to_num(lm[:, :, 3], nan=0.0)

def fill(a):
    a = a.copy(); idx = np.arange(len(a))
    for j in range(a.shape[1]):
        for c in range(a.shape[2]):
            v = a[:, j, c]; ok = ~np.isnan(v)
            if ok.sum() >= 2:
                a[:, j, c] = np.interp(idx, idx[ok], v[ok])
    return a

def medfilt(a, w=5):
    pad = w // 2
    p = np.pad(a, [(pad, pad)] + [(0, 0)] * (a.ndim - 1), mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(p, w, axis=0), axis=-1)

def gauss(a, sigma=2.0):
    r = int(3 * sigma); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    p = np.pad(a, [(r, r)] + [(0, 0)] * (a.ndim - 1), mode="edge")
    out = np.zeros_like(a)
    for i, kv in enumerate(k):
        out += kv * p[i:i + len(a)]
    return out

px = gauss(medfilt(fill(px)), 2.0)
zz = gauss(medfilt(fill(zz[:, :, None])[:, :, 0]), 3.0)
mid = lambda A, a, b: (A[:, a] + A[:, b]) / 2
sh_, hip_ = mid(px, 11, 12), mid(px, 23, 24)
T_all = np.linalg.norm(sh_ - hip_, axis=1)
lift = (hip_[:, 1] - sh_[:, 1]) / np.maximum(T_all, 1.0)

lying = lift < 0.2
cycles, i = [], 0
while i < N - 1:
    if lying[i]:
        j = i + 1
        while j < N and not lying[j]:
            j += 1
        if j > i + 1 and j < N and lift[i + 1:j].max() > 0.7 and 1.2 <= (t[j] - t[i]) <= 5:
            cycles.append((i, j))
        i = j
    else:
        i += 1
jit = lambda c: float(np.abs(np.diff(px[c[0]:c[1] + 1], 2, axis=0)).mean())
a, b = min(cycles, key=jit)
P = px[a:b + 1]; Z = zz[a:b + 1]; V = vis[a:b + 1]; LF = lift[a:b + 1]
n0 = len(P)
print("ciclo", round(t[a], 2), "->", round(t[b], 2), "s")

# fotogramas clave: inicio (tumbado) y esfuerzo (primer fotograma con la elevacion pedida)
k0 = int(np.argmin(LF[:max(3, n0 // 5)]))
k1 = int(np.argmax(LF >= TARGET_LIFT))
print("fotogramas clave:", k0, k1, "elevacion", round(float(LF[k0]), 2), round(float(LF[k1]), 2))
win = lambda k: slice(max(0, k - 2), min(n0, k + 3))

SIDEIDX = {"L": dict(sh=11, el=13, wr=15, hp=23, kn=25, an=27, he=29, to=31, ear=7),
           "R": dict(sh=12, el=14, wr=16, hp=24, kn=26, an=28, he=30, to=32, ear=8)}

# ====================================================================== piernas y pelvis ESTATICAS (iguales en las dos imagenes)
leg = {sd: {k: np.median(P[:, S[k]], axis=0) for k in ("hp", "kn", "an", "he", "to")} for sd, S in SIDEIDX.items()}
pelv = (leg["L"]["hp"] + leg["R"]["hp"]) / 2
Lt = float(np.median(np.linalg.norm(((P[:, 11] + P[:, 12]) / 2) - ((P[:, 23] + P[:, 24]) / 2), axis=1)))
T = Lt

def torso_frame(k):
    sm = np.mean((P[win(k), 11] + P[win(k), 12]) / 2, axis=0)
    hm = np.mean((P[win(k), 23] + P[win(k), 24]) / 2, axis=0)
    u = (sm - hm) / (np.linalg.norm(sm - hm) + 1e-9)
    return u, np.array([-u[1], u[0]])

# desplazamientos fijos de los hombros respecto al centro de hombros, en el marco del torso
sh_off = {}
for sd, S in SIDEIDX.items():
    rel = []
    for k in range(n0):
        u, n = torso_frame(k); sm = (P[k, 11] + P[k, 12]) / 2
        v = P[k, S["sh"]] - sm; rel.append([v @ u, v @ n])
    sh_off[sd] = np.median(rel, axis=0)
alen = {}
for sd, S in SIDEIDX.items():
    alen[sd] = (float(np.percentile(np.linalg.norm(P[:, S["el"]] - P[:, S["sh"]], axis=1), 70)),
                float(np.percentile(np.linalg.norm(P[:, S["wr"]] - P[:, S["el"]], axis=1), 70)))

def ik(sh, wr, el_ref, l1, l2):
    """Codo de un brazo con huesos rigidos: la solucion mas cercana al codo detectado."""
    v = wr - sh; dd = np.linalg.norm(v) + 1e-9
    dd = float(np.clip(dd, abs(l1 - l2) + 1e-3, l1 + l2 - 1e-3)); u = v / (np.linalg.norm(v) + 1e-9)
    wr = sh + u * dd
    a_ = (l1 ** 2 - l2 ** 2 + dd ** 2) / (2 * dd); h = np.sqrt(max(l1 ** 2 - a_ ** 2, 0))
    base = sh + u * a_; perp = np.array([-u[1], u[0]])
    c1, c2 = base + perp * h, base - perp * h
    return (c1 if np.linalg.norm(c1 - el_ref) < np.linalg.norm(c2 - el_ref) else c2), wr

def build_pose(k):
    u, n = torso_frame(k)
    sm = pelv + u * Lt
    pose = np.zeros((33, 2)); vv = np.ones(33)
    for sd, S in SIDEIDX.items():
        for key in ("hp", "kn", "an", "he", "to"):
            pose[S[key]] = leg[sd][key]
        shp = sm + u * sh_off[sd][0] + n * sh_off[sd][1]
        pose[S["sh"]] = shp
        wr = np.mean(P[win(k), S["wr"]], axis=0); el = np.mean(P[win(k), S["el"]], axis=0)
        e, w2 = ik(shp, wr, el, *alen[sd])
        pose[S["el"]], pose[S["wr"]] = e, w2
    # cabeza (centro del craneo) y direccion de la cara
    ear = np.mean((P[win(k), 7] + P[win(k), 8]) / 2, axis=0); nose = np.mean(P[win(k), 0], axis=0)
    head = ear + (nose - ear) * 0.30
    pose[0] = nose; pose[7] = pose[8] = head
    return pose

PP = np.stack([build_pose(k0), build_pose(k1)])
ZZ = np.tile(np.median(Z, axis=0), (2, 1)); VV = np.ones((2, 33))
zL = float(np.median(ZZ[:, [11, 13, 23, 25]])); zR = float(np.median(ZZ[:, [12, 14, 24, 26]]))
FAR, NEAR = ("R", "L") if zL < zR else ("L", "R")

# ---- suelo: pies y gluteo apoyados al 100% en la misma linea
HIPS = [23, 24]
GROUND_Y = float(max(PP[:, 23, 1].max(), PP[:, 24, 1].max())) + 0.205 * T       # fondo del gluteo
def _rot(p, c, th):
    d_ = p - c; cs, sn = np.cos(th), np.sin(th)
    return c + np.array([d_[0] * cs - d_[1] * sn, d_[0] * sn + d_[1] * cs])
for sd, S in SIDEIDX.items():
    base = PP[0].copy()
    def bottom(th):
        he, to = _rot(base[S["he"]], base[S["kn"]], th), _rot(base[S["to"]], base[S["kn"]], th)
        return max(he[1], to[1]) + 0.03 * T
    ths = np.linspace(-0.6, 0.6, 1201)
    th_best = ths[np.argmin([abs(bottom(t_) - GROUND_Y) for t_ in ths])]
    for kk in range(2):
        for key in ("an", "he", "to"):
            PP[kk, S[key]] = _rot(PP[kk, S[key]], PP[kk, S["kn"]], th_best)
FLOOR_LINE_Y = GROUND_Y + 0.052 * T

# lado "delantero" del torso (hacia donde mira la cara)
fdots = []
for k in (k0, k1):
    u, n = torso_frame(k)
    sm = pelv + u * Lt
    fdots.append(float((PP[0 if k == k0 else 1][0] - sm) @ n))
FRONT = 1.0 if np.mean(fdots) >= 0 else -1.0

# ====================================================================== encuadre comun a las dos imagenes
pts = PP[:, [0, 7, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]].reshape(-1, 2)
x0, y0 = pts.min(0); x1, y1 = pts.max(0)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
MARG = 0.36 * T
scale = min(CW * SS / (x1 - x0 + 2 * MARG), CH * SS / (y1 - y0 + 2 * MARG))
LW = max(0.052 * T * scale, 3.0 * SS)
LI = max(0.026 * T * scale, 1.6 * SS)
floor_world = float(PP[:, [23, 24, 27, 28, 29, 30, 31, 32], 1].max())

def C(p):
    p = np.asarray(p, float)
    return np.stack([(p[..., 0] - cx) * scale + CW * SS / 2, (p[..., 1] - cy) * scale + CH * SS / 2], -1)

def circ(img, c, r, col):
    cc = C(c); cv2.circle(img, (int(round(cc[0])), int(round(cc[1]))), max(1, int(round(r * scale))), col, -1, cv2.LINE_AA)

def circ_px(img, c, rpx, col):
    cc = C(c); cv2.circle(img, (int(round(cc[0])), int(round(cc[1]))), max(1, int(round(rpx))), col, -1, cv2.LINE_AA)

def poly_px(poly):
    return np.round(C(poly)).astype(np.int32)

def paint(img, shapes, fillcol=WHITE):
    """Un grupo de formas = una sola silueta con contorno continuo (sin lineas en las articulaciones)."""
    for sh in shapes:
        if sh[0] == "c":
            circ_px(img, sh[1], sh[2] * scale + LW, INK)
        else:
            pp = poly_px(sh[1]); cv2.fillPoly(img, [pp], INK, cv2.LINE_AA)
            cv2.polylines(img, [pp], True, INK, int(round(2 * LW)), cv2.LINE_AA)
    for sh in shapes:
        if sh[0] == "c":
            circ(img, sh[1], sh[2], fillcol)
        else:
            cv2.fillPoly(img, [poly_px(sh[1])], fillcol, cv2.LINE_AA)

def line(img, pts_, w=None, col=INK):
    arr = poly_px(np.asarray(pts_, float)); ww = int(round(w or LI))
    cv2.polylines(img, [arr], False, col, ww, cv2.LINE_AA)
    for e in (arr[0], arr[-1]):
        cv2.circle(img, (int(e[0]), int(e[1])), max(1, ww // 2), col, -1, cv2.LINE_AA)

def smooth_curve(pts_, n=24):
    """Curva suave (Catmull-Rom) por los puntos dados."""
    p = np.asarray(pts_, float)
    if len(p) < 3:
        return p
    p = np.vstack([p[0], p, p[-1]]); out = []
    for i in range(1, len(p) - 2):
        for s in np.linspace(0, 1, max(4, n // (len(p) - 3)), endpoint=False):
            out.append(0.5 * ((2 * p[i]) + (-p[i - 1] + p[i + 1]) * s + (2 * p[i - 1] - 5 * p[i] + 4 * p[i + 1] - p[i + 2]) * s ** 2
                              + (-p[i - 1] + 3 * p[i] - 3 * p[i + 1] + p[i + 2]) * s ** 3))
    out.append(p[-2])
    return np.array(out)

def tube(p, q, r0, r1, bulge=0.0, peak=0.5, n=26, caps=True):
    """Extremidad con perfil muscular: poligono con bordes suaves + circulos en las articulaciones."""
    p = np.asarray(p, float); q = np.asarray(q, float); v = q - p; L = np.linalg.norm(v) + 1e-9; u = v / L
    nn = np.array([-u[1], u[0]]); s = np.linspace(0, 1, n)
    r = (r0 + (r1 - r0) * s) * (1 + bulge * np.sin(np.pi * s ** (np.log(0.5) / np.log(peak)))) * T
    c = p[None] + v[None] * s[:, None]
    poly = np.vstack([c + nn * r[:, None], (c - nn * r[:, None])[::-1]])
    out = [("p", poly)]
    if caps:
        out += [("c", p, r[0]), ("c", q, r[-1])]
    return out

def foot_poly(an, he, to):
    d_ = to - he; L = np.linalg.norm(d_) + 1e-9; dr = d_ / L; up = np.array([-dr[1], dr[0]])
    if up[1] > 0:
        up = -up
    t_ = T
    P_ = [he - dr * 0.035 * t_, to + dr * 0.04 * t_, to + dr * 0.03 * t_ + up * 0.045 * t_,
          he + dr * 0.80 * L + up * 0.072 * t_, he + dr * 0.50 * L + up * 0.105 * t_,
          an + dr * 0.05 * t_ + up * 0.0, an - dr * 0.075 * t_ + up * 0.02 * t_,
          he - dr * 0.035 * t_ + up * 0.075 * t_]
    return np.array(P_)

_prev = {}
def side_normal(key, p, q, hint):
    v = q - p; v = v / (np.linalg.norm(v) + 1e-9); n_ = np.array([-v[1], v[0]])
    ref = _prev.get(key, hint)
    if n_ @ ref < 0:
        n_ = -n_
    _prev[key] = n_
    return n_

def render(k, tag):
    f = PP[k]; g = lambda j: f[j]
    img = np.full((CH * SS, CW * SS, 3), 255, np.uint8)
    fy = C((0, FLOOR_LINE_Y))[1]
    cv2.line(img, (0, int(fy)), (CW * SS, int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)
    sm = (g(11) + g(12)) / 2; hm = (g(23) + g(24)) / 2
    ax = hm - sm; L = np.linalg.norm(ax) + 1e-9; u = ax / L; nrm = np.array([-u[1], u[0]])
    fnorm = nrm * FRONT                                             # hacia la barriga
    hint = fnorm

    def draw_leg(sd):
        S = SIDEIDX[sd]; hp, kn, an, he, to = g(S["hp"]), g(S["kn"]), g(S["an"]), g(S["he"]), g(S["to"])
        shapes = tube(hp, kn, 0.20, 0.135, bulge=0.09, peak=0.4) + tube(kn, an, 0.135, 0.072, bulge=0.24, peak=0.27)
        shapes.append(("p", foot_poly(an, he, to)))
        paint(img, shapes)
        n1 = side_normal(sd + "th", hp, kn, hint); n2 = side_normal(sd + "sk", kn, an, hint)
        tv = (kn - hp) / (np.linalg.norm(kn - hp) + 1e-9); sv = (an - kn) / (np.linalg.norm(an - kn) + 1e-9)
        # cuadriceps y rotula
        line(img, smooth_curve([hp + (kn - hp) * 0.45 + n1 * 0.085 * T, hp + (kn - hp) * 0.70 + n1 * 0.10 * T, hp + (kn - hp) * 0.93 + n1 * 0.07 * T]))
        line(img, smooth_curve([kn + sv * 0.025 * T + n1 * 0.075 * T, kn + sv * 0.07 * T + n1 * 0.045 * T, kn + sv * 0.03 * T + n1 * 0.00 * T]))
        # gemelo y tibia
        line(img, smooth_curve([kn + sv * 0.07 * T - n2 * 0.07 * T, kn + (an - kn) * 0.30 - n2 * 0.085 * T, kn + (an - kn) * 0.58 - n2 * 0.055 * T]))
        line(img, [kn + (an - kn) * 0.30 + n2 * 0.045 * T, kn + (an - kn) * 0.78 + n2 * 0.035 * T], w=LI * 0.8)
        # dedos
        dr = (to - he) / (np.linalg.norm(to - he) + 1e-9); up = np.array([-dr[1], dr[0]]); up = -up if up[1] > 0 else up
        for off in (0.05, 0.095):
            line(img, [to - dr * off * T + up * 0.04 * T, to - dr * off * T + up * 0.0 * T], w=LI * 0.8)

    def draw_arm(sd):
        S = SIDEIDX[sd]; s_, e_, w_ = g(S["sh"]), g(S["el"]), g(S["wr"])
        shapes = [("c", s_, 0.145)] + tube(s_, e_, 0.125, 0.095, bulge=0.17, peak=0.42) + tube(e_, w_, 0.095, 0.085, bulge=0.13, peak=0.3)
        paint(img, shapes)
        n1 = side_normal(sd + "ua", s_, e_, hint); n2 = side_normal(sd + "fa", e_, w_, hint)
        line(img, smooth_curve([s_ + (e_ - s_) * 0.22 + n1 * 0.045 * T, s_ + (e_ - s_) * 0.50 + n1 * 0.062 * T, s_ + (e_ - s_) * 0.80 + n1 * 0.03 * T]))   # biceps
        line(img, smooth_curve([s_ + (e_ - s_) * 0.12 - n1 * 0.07 * T, s_ + (e_ - s_) * 0.45 - n1 * 0.075 * T, s_ + (e_ - s_) * 0.75 - n1 * 0.045 * T]))   # triceps
        line(img, smooth_curve([s_ + n1 * 0.10 * T, s_ + (e_ - s_) * 0.18 + n1 * 0.095 * T, s_ + (e_ - s_) * 0.28 + n1 * 0.06 * T]), w=LI * 0.9)             # deltoides
        line(img, smooth_curve([e_ + (w_ - e_) * 0.12 + n2 * 0.035 * T, e_ + (w_ - e_) * 0.42 + n2 * 0.045 * T, e_ + (w_ - e_) * 0.78 + n2 * 0.02 * T]))    # antebrazo
        fv = (w_ - e_) / (np.linalg.norm(w_ - e_) + 1e-9); fc = w_ + fv * 0.05 * T
        fist = [("c", w_ + fv * 0.02 * T, 0.105)]
        pass
        fn = np.array([-fv[1], fv[0]])

    # ---------- orden de dibujo: lado lejano, torso, cuello+cabeza, lado cercano
    draw_leg(FAR); draw_arm(FAR)

    # torso con perfil delantero/trasero
    rf = [(-0.14, .13), (0.0, .21), (0.12, .30), (0.26, .32), (0.46, .24), (0.70, .20), (1.0, .235), (1.12, .245)]
    rb = [(-0.14, .13), (0.0, .19), (0.12, .26), (0.30, .25), (0.52, .20), (0.76, .18), (1.0, .225), (1.12, .235)]
    S_ = np.linspace(-0.14, 0.90, 30)
    rf = [(a, b * 1.22) for a, b in rf]; rb = [(a, b * 1.18) for a, b in rb]
    Rf = np.interp(S_, [p_[0] for p_ in rf], [p_[1] for p_ in rf]) * T
    Rb = np.interp(S_, [p_[0] for p_ in rb], [p_[1] for p_ in rb]) * T
    def _sm(a, w=7):
        k = np.hanning(w + 2)[1:-1]; k /= k.sum(); pd = np.pad(a, w // 2, mode="edge"); return np.convolve(pd, k, mode="valid")
    Rf = _sm(Rf); Rb = _sm(Rb)
    c_ = np.array([sm + u * L * s for s in S_])
    poly = np.vstack([c_ + fnorm * Rf[:, None], (c_ - fnorm * Rb[:, None])[::-1]])
    paint(img, [("p", poly)])
    edge_f = lambda s: sm + u * L * s + fnorm * np.interp(s, [p_[0] for p_ in rf], [p_[1] for p_ in rf]) * T
    edge_b = lambda s: sm + u * L * s - fnorm * np.interp(s, [p_[0] for p_ in rb], [p_[1] for p_ in rb]) * T
    # musculatura del torso
    line(img, smooth_curve([edge_f(0.14) - fnorm * 0.005 * T, edge_f(0.22) - fnorm * 0.09 * T, edge_f(0.33) - fnorm * 0.13 * T, edge_f(0.40) - fnorm * 0.09 * T]))  # pectoral
    for s_ in (0.46, 0.56, 0.66):                                                                                                                                   # abdominales
        line(img, smooth_curve([edge_f(s_) - fnorm * 0.025 * T, edge_f(s_) - fnorm * 0.08 * T, edge_f(s_) - fnorm * 0.12 * T]), w=LI)
    line(img, [sm + u * L * 0.44 - fnorm * 0.10 * T, sm + u * L * 0.68 - fnorm * 0.10 * T], w=LI * 0.9)                                                             # linea alba
    line(img, smooth_curve([edge_b(0.10) + fnorm * 0.07 * T, edge_b(0.30) + fnorm * 0.11 * T, edge_b(0.52) + fnorm * 0.09 * T]), w=LI * 0.9)                       # dorsal
    line(img, smooth_curve([edge_b(0.0) + fnorm * 0.03 * T, edge_b(0.07) + fnorm * 0.08 * T, edge_b(0.16) + fnorm * 0.08 * T]), w=LI * 0.9)                         # trapecio

    # cuello y cabeza (perfil generico, sin rasgos personales)
    ear = (g(7) + g(8)) / 2; head = ear; noseP = g(0)
    v = head - sm; v = v / (np.linalg.norm(v) + 1e-9)
    paint(img, tube(sm + u * -0.02 * L, sm + (head - sm) * 0.80, 0.125, 0.105, caps=False))
    face = noseP - ear; face = face / (np.linalg.norm(face) + 1e-9)
    ang_ax = np.arctan2(v[1], v[0]); ang_face = np.arctan2(face[1], face[0])
    th_ = np.linspace(0, 2 * np.pi, 120, endpoint=False)
    ra, rb_ = 0.30 * T, 0.245 * T
    rad = ra * rb_ / np.sqrt((rb_ * np.cos(th_)) ** 2 + (ra * np.sin(th_)) ** 2)                      # ovalo con eje mayor en v
    dth = lambda a: np.angle(np.exp(1j * (th_ + ang_ax - a)))                                          # angulo respecto a una direccion
    rad = rad + 0.040 * T * np.exp(-(dth(ang_face) / 0.20) ** 2)                                       # nariz
    rad = rad + 0.030 * T * np.exp(-(dth(ang_face + np.sign(np.sin(ang_face - ang_ax) + 1e-9) * 0.55) / 0.30) ** 2)   # mandibula
    hc = head + v * 0.035 * T
    hpoly = hc + np.stack([rad * np.cos(th_ + ang_ax), rad * np.sin(th_ + ang_ax)], 1)
    paint(img, [("p", hpoly)])
    # oreja: arco abierto hacia la cara, detras del centro
    earc = hc - face * 0.075 * T
    aa = np.linspace(ang_face + 0.9, ang_face + 2 * np.pi - 0.9, 14)

    draw_leg(NEAR)
    # ---- pantalon corto: una sola silueta organica (casco convexo de cintura + cadera + dobladillo)
    Sn = SIDEIDX[NEAR]; hpN, knN = g(Sn["hp"]), g(Sn["kn"])
    end = hpN + (knN - hpN) * 0.52
    tv = (end - hpN) / (np.linalg.norm(end - hpN) + 1e-9); tn = np.array([-tv[1], tv[0]])
    sw = 0.84
    wf = np.interp(sw, [p_[0] for p_ in rf], [p_[1] for p_ in rf]) * T * 1.06
    wb = np.interp(sw, [p_[0] for p_ in rb], [p_[1] for p_ in rb]) * T * 1.06
    wc = sm + u * L * sw
    pts_h = [wc + fnorm * wf, wc - fnorm * wb]
    for s2 in (0.96, 1.04):                                                        # que cubra el final del torso sin cuadrados
        w2 = sm + u * L * s2
        pts_h += [w2 + fnorm * wf * 0.96, w2 - fnorm * wb * 0.96]
    for a_ in np.linspace(0, 2 * np.pi, 28, endpoint=False):                     # cadera / gluteo redondeado
        pts_h.append(hpN - tv * 0.02 * T + 0.205 * T * np.array([np.cos(a_), np.sin(a_)]))
    hemw = 0.205 * T
    for sgn in (1, -1):                                                           # dobladillo con esquinas redondeadas
        for a_ in np.linspace(0, 2 * np.pi, 10, endpoint=False):
            pts_h.append(end + tn * sgn * (hemw - 0.035 * T) + 0.035 * T * np.array([np.cos(a_), np.sin(a_)]))
    hull = cv2.convexHull(np.array(pts_h, np.float32)).reshape(-1, 2)
    paint(img, [("p", hull)], SHORTS)
    line(img, smooth_curve([hpN + tv * 0.10 * T + tn * 0.15 * T, hpN + tv * 0.20 * T + tn * 0.05 * T, hpN + tv * 0.34 * T + tn * 0.0]), w=LI * 0.9)  # pliegue
    line(img, [end - tv * 0.035 * T + tn * (hemw - 0.02 * T), end - tv * 0.035 * T - tn * (hemw - 0.02 * T)], w=LI * 0.9)  # dobladillo
    draw_arm(NEAR)
    return cv2.resize(img, (CW, CH), interpolation=cv2.INTER_AREA)

f1, f2 = render(0, "inicio"), render(1, "esfuerzo")
cv2.imwrite(BASE + "_1.png", f1); cv2.imwrite(BASE + "_2.png", f2)
cv2.imwrite(BASE + "_par.png", np.hstack([f1, f2]))
rgb = [Image.fromarray(cv2.cvtColor(f_, cv2.COLOR_BGR2RGB)) for f_ in (f1, f2)]
mont = Image.new("RGB", (CW, CH * 2)); mont.paste(rgb[0], (0, 0)); mont.paste(rgb[1], (0, CH))
pal = mont.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
pil = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in rgb]
pil[0].save(BASE + ".gif", save_all=True, append_images=pil[1:], duration=[1100, 1100], loop=0, optimize=True, disposal=1)
print("GIF", BASE + ".gif", os.path.getsize(BASE + ".gif") // 1024, "KB")
