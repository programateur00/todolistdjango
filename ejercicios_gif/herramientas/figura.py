"""Muñequito line-art (mismo estilo que situps.gif) dirigido por poses de esqueleto.
Coordenadas de autoría: x derecha, y ARRIBA, ángulos matemáticos (0=derecha, 90=arriba), T = largo del torso = 1.
"""
import numpy as np, cv2, os
from PIL import Image

CW, CH, SS = 480, 360, 3
INK, WHITE, SHORTS, FLOOR = (24, 24, 24), (255, 255, 255), (238, 238, 238), (200, 200, 200)
GREY_ARROW = (150, 150, 150)

L_THIGH, L_SHIN, L_UA, L_FA = 0.95, 0.92, 0.62, 0.56
NECK_HEAD = 0.52


def dv(deg):
    a = np.deg2rad(deg)
    return np.array([np.cos(a), np.sin(a)])


def ang(v):
    return float(np.rad2deg(np.arctan2(v[1], v[0])))


def rot(v, deg):
    a = np.deg2rad(deg); c, s = np.cos(a), np.sin(a)
    return np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])


def ik2(root, target, l1, l2, bend):
    """Articulación intermedia de 2 huesos. bend='cw'|'ccw' = lado hacia el que se dobla."""
    root = np.asarray(root, float); target = np.asarray(target, float)
    v = target - root; d = np.linalg.norm(v) + 1e-9
    d = float(np.clip(d, abs(l1 - l2) + 1e-3, l1 + l2 - 1e-3)); u = v / (np.linalg.norm(v) + 1e-9)
    a_ = (l1 ** 2 - l2 ** 2 + d ** 2) / (2 * d); h = np.sqrt(max(l1 ** 2 - a_ ** 2, 0))
    perp = np.array([-u[1], u[0]])  # ccw
    mid = root + u * a_ + perp * h * (1 if bend == 'ccw' else -1)
    return mid, root + u * d


# ====================================================================== construcción de poses
def limb_arm(spec, S, hd, bel):
    kind = spec[0]
    if kind == 'fk':
        e = S + dv(spec[1]) * L_UA; w = e + dv(spec[2]) * L_FA
    elif kind == 'ik':
        e, w = ik2(S, spec[1], L_UA, L_FA, spec[2])
    elif kind == 'ikh':  # muñeca relativa al centro de la cabeza: du a lo largo de la cabeza, dn hacia la barriga
        hu = (hd - S) / (np.linalg.norm(hd - S) + 1e-9)
        tgt = hd + hu * spec[1] + bel * spec[2]
        e, w = ik2(S, tgt, L_UA, L_FA, spec[3])
    elif kind == 'ikr':  # muñeca relativa al hombro (coordenadas absolutas de desplazamiento)
        e, w = ik2(S, S + np.array(spec[1]), L_UA, L_FA, spec[2])
    else:
        raise ValueError(kind)
    return S, e, w


def limb_leg(spec, H):
    kind = spec[0]
    if kind == 'fk':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN; foot = spec[3]
    elif kind == 'ik':
        k, a = ik2(H, spec[1], L_THIGH, L_SHIN, spec[2]); foot = spec[3]
    elif kind == 'ikr':
        k, a = ik2(H, H + np.array(spec[1]), L_THIGH, L_SHIN, spec[2]); foot = spec[3]
    else:
        raise ValueError(kind)
    d = dv(foot); p = rot(d, -90)  # p = hacia "abajo" respecto al pie
    he = a + p * 0.10 - d * 0.07
    to = he + d * 0.44
    return H, k, a, he, to


def build_side(p):
    f = p.get('f', 1)
    t = p['torso']
    if 'sh' in p:
        H = np.array(p['sh'], float) - dv(t)
    else:
        H = np.array(p['hip'], float)
    S = H + dv(t)
    hdir = p.get('head', t)
    hd = S + dv(hdir) * NECK_HEAD
    b0 = 0 if f > 0 else 180
    bel = dv(b0 + (t - 90))
    face = dv(b0 + (hdir - 90))
    J = dict(H=H, S=S, hd=hd, bel=bel, face=face, hdir=hdir, f=f)
    for side in ('near', 'far'):
        J[side + '_arm'] = limb_arm(p[side + '_arm'], S, hd, bel)
        J[side + '_leg'] = limb_leg(p[side + '_leg'], H)
        if side + '_hand' in p:
            w = J[side + '_arm'][2]
            J[side + '_handtip'] = w + dv(p[side + '_hand']) * 0.30
    return J


def ground_shift(J):
    """cuánto subir/bajar para que lo más bajo toque y=0"""
    lows = []
    lows.append(J['H'][1] - 0.20)
    lows.append(J['hd'][1] - 0.27)
    lows.append(J['S'][1] - 0.15)
    for s in ('near', 'far'):
        hp, k, a, he, to = J[s + '_leg']
        lows += [k[1] - 0.13, he[1] - 0.04, to[1] - 0.04, a[1] - 0.07]
        sh, e, w = J[s + '_arm']
        lows += [e[1] - 0.095, w[1] - 0.09]
    return -min(lows)


def shift_J(J, dy):
    out = {}
    for k, v in J.items():
        if isinstance(v, np.ndarray):
            out[k] = v + np.array([0, dy]) if k in ('H', 'S', 'hd', 'near_handtip', 'far_handtip') else v
        elif isinstance(v, tuple):
            out[k] = tuple(x + np.array([0, dy]) for x in v)
        else:
            out[k] = v
    return out


def all_points(J):
    pts = [J['H'], J['S'], J['hd']]
    for s in ('near', 'far'):
        pts += list(J[s + '_arm']) + list(J[s + '_leg'])
        if s + '_handtip' in J:
            pts.append(J[s + '_handtip'])
    return np.array(pts)


# ====================================================================== lienzo
class Canvas:
    def __init__(self, bbox, floor_y=None, margin=0.45, aspect_pad=(0, 0)):
        x0, y0, x1, y1 = bbox  # math coords
        self.floor_y = floor_y
        w = (x1 - x0) + 2 * margin; h = (y1 - y0) + 2 * margin
        self.scale = min(CW * SS / w, CH * SS / h)
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.LW = max(0.052 * self.scale, 3.0 * SS)
        self.LI = max(0.026 * self.scale, 1.6 * SS)

    def C(self, p):
        p = np.asarray(p, float)
        return np.stack([(p[..., 0] - self.cx) * self.scale + CW * SS / 2,
                         -(p[..., 1] - self.cy) * self.scale + CH * SS / 2], -1)


class Pen:
    def __init__(self, cv_, img):
        self.c = cv_; self.img = img; self.prev = {}

    def circ_px(self, c, rpx, col):
        cc = self.c.C(c); cv2.circle(self.img, (int(round(cc[0])), int(round(cc[1]))), max(1, int(round(rpx))), col, -1, cv2.LINE_AA)

    def paint(self, shapes, fillcol=WHITE):
        c = self.c
        for sh in shapes:
            if sh[0] == 'c':
                self.circ_px(sh[1], sh[2] * c.scale + c.LW, INK)
            else:
                pp = np.round(c.C(sh[1])).astype(np.int32)
                cv2.fillPoly(self.img, [pp], INK, cv2.LINE_AA)
                cv2.polylines(self.img, [pp], True, INK, int(round(2 * c.LW)), cv2.LINE_AA)
        for sh in shapes:
            if sh[0] == 'c':
                self.circ_px(sh[1], sh[2] * c.scale, fillcol)
            else:
                cv2.fillPoly(self.img, [np.round(c.C(sh[1])).astype(np.int32)], fillcol, cv2.LINE_AA)

    def line(self, pts, w=None, col=INK):
        arr = np.round(self.c.C(np.asarray(pts, float))).astype(np.int32); ww = int(round(w or self.c.LI))
        cv2.polylines(self.img, [arr], False, col, ww, cv2.LINE_AA)
        for e in (arr[0], arr[-1]):
            cv2.circle(self.img, (int(e[0]), int(e[1])), max(1, ww // 2), col, -1, cv2.LINE_AA)

    def side_normal(self, key, p, q, hint):
        v = q - p; v = v / (np.linalg.norm(v) + 1e-9); n_ = np.array([-v[1], v[0]])
        ref = self.prev.get(key, hint)
        if n_ @ ref < 0:
            n_ = -n_
        self.prev[key] = n_
        return n_


def smooth_curve(pts_, n=24):
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
    p = np.asarray(p, float); q = np.asarray(q, float); v = q - p; L = np.linalg.norm(v) + 1e-9; u = v / L
    nn = np.array([-u[1], u[0]]); s = np.linspace(0, 1, n)
    r = (r0 + (r1 - r0) * s) * (1 + bulge * np.sin(np.pi * s ** (np.log(0.5) / np.log(peak))))
    c = p[None] + v[None] * s[:, None]
    poly = np.vstack([c + nn * r[:, None], (c - nn * r[:, None])[::-1]])
    out = [('p', poly)]
    if caps:
        out += [('c', p, r[0]), ('c', q, r[-1])]
    return out


def foot_poly(an, he, to):
    d_ = to - he; L = np.linalg.norm(d_) + 1e-9; dr = d_ / L; up = np.array([-dr[1], dr[0]])
    if up[1] < 0:  # eje y arriba: "arriba" del pie = y positivo
        up = -up
    t_ = 1.0
    P_ = [he - dr * 0.035 * t_, to + dr * 0.04 * t_, to + dr * 0.03 * t_ + up * 0.045 * t_,
          he + dr * 0.80 * L + up * 0.072 * t_, he + dr * 0.50 * L + up * 0.105 * t_,
          an + dr * 0.05 * t_, an - dr * 0.075 * t_ + up * 0.02 * t_,
          he - dr * 0.035 * t_ + up * 0.075 * t_]
    return np.array(P_)


# ====================================================================== dibujo vista lateral
def draw_side(pen, J, props_back=None):
    c = pen.c; pen.prev = {}
    f = J['f']; S, H, hd = J['S'], J['H'], J['hd']
    bel = J['bel']; hint = bel
    ax = H - S; L = np.linalg.norm(ax) + 1e-9; u = ax / L  # de hombros a cadera

    def draw_leg(sd):
        hp, kn, an, he, to = J[sd + '_leg']
        shapes = tube(hp, kn, 0.20, 0.135, bulge=0.09, peak=0.4) + tube(kn, an, 0.135, 0.072, bulge=0.24, peak=0.27)
        shapes.append(('p', foot_poly(an, he, to)))
        pen.paint(shapes)
        n1 = pen.side_normal(sd + 'th', hp, kn, hint); n2 = pen.side_normal(sd + 'sk', kn, an, hint)
        sv = (an - kn) / (np.linalg.norm(an - kn) + 1e-9)
        pen.line(smooth_curve([hp + (kn - hp) * 0.45 + n1 * 0.085, hp + (kn - hp) * 0.70 + n1 * 0.10, hp + (kn - hp) * 0.93 + n1 * 0.07]))
        pen.line(smooth_curve([kn + sv * 0.025 + n1 * 0.075, kn + sv * 0.07 + n1 * 0.045, kn + sv * 0.03]))
        pen.line(smooth_curve([kn + sv * 0.07 - n2 * 0.07, kn + (an - kn) * 0.30 - n2 * 0.085, kn + (an - kn) * 0.58 - n2 * 0.055]))
        pen.line([kn + (an - kn) * 0.30 + n2 * 0.045, kn + (an - kn) * 0.78 + n2 * 0.035], w=c.LI * 0.8)
        dr = (to - he) / (np.linalg.norm(to - he) + 1e-9); up = np.array([-dr[1], dr[0]]); up = -up if up[1] < 0 else up
        for off in (0.05, 0.095):
            pen.line([to - dr * off + up * 0.04, to - dr * off], w=c.LI * 0.8)

    def draw_arm(sd):
        s_, e_, w_ = J[sd + '_arm']
        shapes = [('c', s_, 0.145)] + tube(s_, e_, 0.125, 0.095, bulge=0.17, peak=0.42) + tube(e_, w_, 0.095, 0.085, bulge=0.13, peak=0.3)
        pen.paint(shapes)
        n1 = pen.side_normal(sd + 'ua', s_, e_, hint); n2 = pen.side_normal(sd + 'fa', e_, w_, hint)
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.22 + n1 * 0.045, s_ + (e_ - s_) * 0.50 + n1 * 0.062, s_ + (e_ - s_) * 0.80 + n1 * 0.03]))
        pen.line(smooth_curve([s_ + (e_ - s_) * 0.12 - n1 * 0.07, s_ + (e_ - s_) * 0.45 - n1 * 0.075, s_ + (e_ - s_) * 0.75 - n1 * 0.045]))
        pen.line(smooth_curve([s_ + n1 * 0.10, s_ + (e_ - s_) * 0.18 + n1 * 0.095, s_ + (e_ - s_) * 0.28 + n1 * 0.06]), w=c.LI * 0.9)
        pen.line(smooth_curve([e_ + (w_ - e_) * 0.12 + n2 * 0.035, e_ + (w_ - e_) * 0.42 + n2 * 0.045, e_ + (w_ - e_) * 0.78 + n2 * 0.02]))
        if sd + '_handtip' in J:
            tip = J[sd + '_handtip']
            pen.paint(tube(w_, tip, 0.085, 0.06, bulge=0.1, peak=0.4))

    def shorts(sd, waist):
        hpN, knN = J[sd + '_leg'][0], J[sd + '_leg'][1]
        end = hpN + (knN - hpN) * 0.52
        tv = (end - hpN) / (np.linalg.norm(end - hpN) + 1e-9); tn = np.array([-tv[1], tv[0]])
        pts_h = []
        if waist:
            sw = 0.84
            wf = np.interp(sw, [p_[0] for p_ in RF], [p_[1] for p_ in RF]) * 1.06
            wb = np.interp(sw, [p_[0] for p_ in RB], [p_[1] for p_ in RB]) * 1.06
            wc = S + u * L * sw
            pts_h += [wc + bel * wf, wc - bel * wb]
            for s2 in (0.96, 1.04):
                w2 = S + u * L * s2
                pts_h += [w2 + bel * wf * 0.96, w2 - bel * wb * 0.96]
        for a_ in np.linspace(0, 2 * np.pi, 28, endpoint=False):
            pts_h.append(hpN - tv * 0.02 + 0.205 * np.array([np.cos(a_), np.sin(a_)]))
        hemw = 0.205
        for sgn in (1, -1):
            for a_ in np.linspace(0, 2 * np.pi, 10, endpoint=False):
                pts_h.append(end + tn * sgn * (hemw - 0.035) + 0.035 * np.array([np.cos(a_), np.sin(a_)]))
        hull = cv2.convexHull(np.array(pts_h, np.float32)).reshape(-1, 2)
        pen.paint([('p', hull)], SHORTS)
        pen.line(smooth_curve([hpN + tv * 0.10 + tn * 0.15, hpN + tv * 0.20 + tn * 0.05, hpN + tv * 0.34]), w=c.LI * 0.9)
        pen.line([end - tv * 0.035 + tn * (hemw - 0.02), end - tv * 0.035 - tn * (hemw - 0.02)], w=c.LI * 0.9)

    RF0 = [(-0.14, .13), (0.0, .21), (0.12, .30), (0.26, .32), (0.46, .24), (0.70, .20), (1.0, .235), (1.12, .245)]
    RB0 = [(-0.14, .13), (0.0, .19), (0.12, .26), (0.30, .25), (0.52, .20), (0.76, .18), (1.0, .225), (1.12, .235)]
    RF = [(a, b * 1.22) for a, b in RF0]; RB = [(a, b * 1.18) for a, b in RB0]

    draw_leg('far'); shorts('far', False); draw_arm('far')

    S_ = np.linspace(-0.14, 0.90, 30)
    Rf = np.interp(S_, [p_[0] for p_ in RF], [p_[1] for p_ in RF])
    Rb = np.interp(S_, [p_[0] for p_ in RB], [p_[1] for p_ in RB])

    def _sm(a, w=7):
        k = np.hanning(w + 2)[1:-1]; k /= k.sum(); pd = np.pad(a, w // 2, mode='edge'); return np.convolve(pd, k, mode='valid')
    Rf = _sm(Rf); Rb = _sm(Rb)
    c_ = np.array([S + u * L * s for s in S_])
    poly = np.vstack([c_ + bel * Rf[:, None], (c_ - bel * Rb[:, None])[::-1]])
    pen.paint([('p', poly)])
    edge_f = lambda s: S + u * L * s + bel * np.interp(s, [p_[0] for p_ in RF], [p_[1] for p_ in RF])
    edge_b = lambda s: S + u * L * s - bel * np.interp(s, [p_[0] for p_ in RB], [p_[1] for p_ in RB])
    LI = c.LI
    pen.line(smooth_curve([edge_f(0.14) - bel * 0.005, edge_f(0.22) - bel * 0.09, edge_f(0.33) - bel * 0.13, edge_f(0.40) - bel * 0.09]))
    for s_ in (0.46, 0.56, 0.66):
        pen.line(smooth_curve([edge_f(s_) - bel * 0.025, edge_f(s_) - bel * 0.08, edge_f(s_) - bel * 0.12]), w=LI)
    pen.line([S + u * L * 0.44 - bel * 0.10, S + u * L * 0.68 - bel * 0.10], w=LI * 0.9)
    pen.line(smooth_curve([edge_b(0.10) + bel * 0.07, edge_b(0.30) + bel * 0.11, edge_b(0.52) + bel * 0.09]), w=LI * 0.9)
    pen.line(smooth_curve([edge_b(0.0) + bel * 0.03, edge_b(0.07) + bel * 0.08, edge_b(0.16) + bel * 0.08]), w=LI * 0.9)

    # cuello y cabeza
    v = (hd - S) / (np.linalg.norm(hd - S) + 1e-9)
    pen.paint(tube(S - u * 0.02 * L * -1 * 0 + (-u) * 0.02, S + (hd - S) * 0.80, 0.125, 0.105, caps=False))
    face = J['face']
    ang_ax = np.arctan2(v[1], v[0]); ang_face = np.arctan2(face[1], face[0])
    th_ = np.linspace(0, 2 * np.pi, 120, endpoint=False)
    ra, rb_ = 0.30, 0.245
    rad = ra * rb_ / np.sqrt((rb_ * np.cos(th_)) ** 2 + (ra * np.sin(th_)) ** 2)
    dth = lambda a: np.angle(np.exp(1j * (th_ + ang_ax - a)))
    rad = rad + 0.040 * np.exp(-(dth(ang_face) / 0.20) ** 2)
    rad = rad + 0.030 * np.exp(-(dth(ang_face + np.sign(np.sin(ang_face - ang_ax) + 1e-9) * 0.55) / 0.30) ** 2)
    hc = hd + v * 0.035
    hpoly = hc + np.stack([rad * np.cos(th_ + ang_ax), rad * np.sin(th_ + ang_ax)], 1)
    pen.paint([('p', hpoly)])

    draw_leg('near'); shorts('near', True); draw_arm('near')


# ====================================================================== vista frontal / trasera
def build_front(p):
    H = np.array(p['hip'], float); t = p.get('torso', 90)
    ud = dv(t); S = H + ud
    n = dv(t - 90)  # hacia "R" (imagen derecha cuando está de pie)
    hdir = p.get('head', t)
    hd = S + dv(hdir) * NECK_HEAD
    J = dict(H=H, S=S, n=n, ud=ud, hd=hd, hdir=hdir, back=p.get('back', False), t=t)
    sw = p.get('shoulder_w', 0.34); hw = 0.15
    for sd, sg in (('R', 1), ('L', -1)):
        sh = S + n * sg * sw + p.get('shrug', 0) * ud
        spec = p[sd + '_arm']
        if spec[0] == 'fk':
            e = sh + dv(spec[1]) * L_UA * p.get('fore_' + sd + '_ua', 1.0); w = e + dv(spec[2]) * L_FA * p.get('fore_' + sd + '_fa', 1.0)
        elif spec[0] == 'ik':
            e, w = ik2(sh, spec[1], L_UA, L_FA, spec[2])
        else:
            raise ValueError
        J[sd + '_arm'] = (sh, e, w)
        hp = H + n * sg * hw
        spec = p[sd + '_leg']
        if spec[0] == 'fk':
            k = hp + dv(spec[1]) * L_THIGH * p.get('thigh_' + sd, 1.0); a = k + dv(spec[2]) * L_SHIN * p.get('shin_' + sd, 1.0)
        elif spec[0] == 'ik':
            k, a = ik2(hp, spec[1], L_THIGH, L_SHIN, spec[2])
        else:
            raise ValueError
        J[sd + '_leg'] = (hp, k, a, spec[3] if len(spec) > 3 else sg)  # sg = dirección hacia donde apunta el pie
    return J


def pts_front(J):
    pts = [J['H'], J['S'], J['hd']]
    for sd in 'RL':
        pts += list(J[sd + '_arm']) + list(J[sd + '_leg'][:3])
    return np.array(pts)


def front_shift(J):
    lows = [J['H'][1] - 0.2, J['hd'][1] - 0.28, J['S'][1] - 0.15]
    for sd in 'RL':
        sh, e, w = J[sd + '_arm']; lows += [e[1] - 0.095, w[1] - 0.10]
        hp, k, a, _ = J[sd + '_leg']; lows += [k[1] - 0.13, a[1] - 0.17]
    return -min(lows)


def shift_front(J, dy):
    out = dict(J)
    for k in ('H', 'S', 'hd'):
        out[k] = J[k] + np.array([0, dy])
    for sd in 'RL':
        out[sd + '_arm'] = tuple(x + np.array([0, dy]) for x in J[sd + '_arm'])
        hp, k, a, fd = J[sd + '_leg']
        out[sd + '_leg'] = (hp + np.array([0, dy]), k + np.array([0, dy]), a + np.array([0, dy]), fd)
    return out


def draw_front(pen, J):
    c = pen.c; LI = c.LI
    S, H, n, ud, hd = J['S'], J['H'], J['n'], J['ud'], J['hd']
    back = J['back']
    L = 1.0

    def leg(sd):
        hp, kn, an, fd = J[sd + '_leg']
        sg = 1 if sd == 'R' else -1
        shapes = tube(hp, kn, 0.19, 0.13, bulge=0.07, peak=0.4) + tube(kn, an, 0.13, 0.075, bulge=0.2, peak=0.3)
        # zapatilla vista de frente: óvalo bajo el tobillo hacia fuera
        down = -ud
        foot_c = an + down * 0.10 + n * fd * 0.03
        fv = np.array([fd * 0.0, 0.0])
        th = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        fpoly = np.stack([foot_c[0] + 0.12 * np.cos(th) + 0.0, foot_c[1] + 0.08 * np.sin(th)], 1)
        fpoly[:, 0] += fd * 0.05
        shapes.append(('p', fpoly))
        pen.paint(shapes)
        # músculo
        nn1 = rot((kn - hp) / (np.linalg.norm(kn - hp) + 1e-9), 90)
        pen.line(smooth_curve([hp + (kn - hp) * 0.45 + nn1 * 0.0, hp + (kn - hp) * 0.7, hp + (kn - hp) * 0.92]), w=LI * 0.9)

    def arm(sd):
        sh, e, w = J[sd + '_arm']
        shapes = [('c', sh, 0.145)] + tube(sh, e, 0.125, 0.095, bulge=0.15, peak=0.42) + tube(e, w, 0.095, 0.08, bulge=0.12, peak=0.3)
        shapes.append(('c', w + (w - e) / (np.linalg.norm(w - e) + 1e-9) * 0.05, 0.10))
        pen.paint(shapes)
        nn1 = rot((e - sh) / (np.linalg.norm(e - sh) + 1e-9), 90)
        pen.line(smooth_curve([sh + (e - sh) * 0.25 + nn1 * 0.03, sh + (e - sh) * 0.5 + nn1 * 0.05, sh + (e - sh) * 0.8 + nn1 * 0.02]), w=LI * 0.9)
        nn2 = rot((w - e) / (np.linalg.norm(w - e) + 1e-9), 90)
        pen.line(smooth_curve([e + (w - e) * 0.15 - nn2 * 0.03, e + (w - e) * 0.45 - nn2 * 0.04, e + (w - e) * 0.8 - nn2 * 0.015]), w=LI * 0.9)

    for sd in 'RL':
        leg(sd)
    # pantalón (detrás del torso)
    def shorts_poly():
        pts_h = []
        for sg in (1, -1):
            for s2, wd in ((0.80, 0.27), (1.0, 0.31)):
                pts_h.append(S - ud * 0 + (H - S) * s2 + n * sg * wd)
        for sd in 'RL':
            hp, kn, an, fd = J[sd + '_leg']
            end = hp + (kn - hp) * 0.50
            tv = (end - hp) / (np.linalg.norm(end - hp) + 1e-9); tn = np.array([-tv[1], tv[0]])
            for sg in (1, -1):
                pts_h.append(end + tn * sg * 0.20)
            for a_ in np.linspace(0, 2 * np.pi, 20, endpoint=False):
                pts_h.append(hp + 0.21 * np.array([np.cos(a_), np.sin(a_)]))
        return cv2.convexHull(np.array(pts_h, np.float32)).reshape(-1, 2)

    for sd in 'RL':
        arm(sd) if False else None
    # torso
    S_ = np.linspace(-0.12, 1.02, 30)
    prof = [(-0.12, .15), (0.0, .33), (0.10, .38), (0.25, .35), (0.45, .28), (0.70, .26), (0.9, .29), (1.02, .30)]
    W_ = np.interp(S_, [a for a, b in prof], [b for a, b in prof])
    k = np.hanning(9)[1:-1]; k /= k.sum(); W_ = np.convolve(np.pad(W_, 3, mode='edge'), k, mode='valid')
    ax = H - S
    cc = np.array([S + ax * s for s in S_])
    poly = np.vstack([cc + n * W_[:, None], (cc - n * W_[:, None])[::-1]])
    # cuello
    pen.paint(tube(S + ud * (-0.02), S + (hd - S) * 0.78, 0.115, 0.10, caps=False))
    pen.paint([('p', poly)])
    P_ = lambda s, off: S + ax * s + n * off
    if not back:
        for sg in (1, -1):
            pen.line(smooth_curve([P_(0.30, sg * 0.03), P_(0.30, sg * 0.15), P_(0.24, sg * 0.28)]))      # pectoral inferior
            for s_ in (0.46, 0.57, 0.68):
                pen.line([P_(s_, sg * 0.03), P_(s_, sg * 0.11)], w=LI)
        pen.line([P_(0.38, 0), P_(0.78, 0)], w=LI * 0.9)
        pen.line(smooth_curve([P_(0.05, -0.12), P_(0.0, 0.0), P_(0.05, 0.12)]), w=LI * 0.9)             # clavículas
    else:
        pen.line([P_(0.02, 0), P_(0.95, 0)], w=LI * 0.9)
        for sg in (1, -1):
            pen.line(smooth_curve([P_(0.12, sg * 0.08), P_(0.25, sg * 0.18), P_(0.40, sg * 0.12)]), w=LI * 0.9)
    hull = shorts_poly()
    pen.paint([('p', hull)], SHORTS)
    pen.line([P_(1.0, -0.30), P_(1.0, 0.30)], w=LI * 0.9)
    # cabeza (óvalo)
    v = (hd - S) / (np.linalg.norm(hd - S) + 1e-9)
    th_ = np.linspace(0, 2 * np.pi, 80, endpoint=False)
    pv = np.array([-v[1], v[0]])
    hc = hd + v * 0.035
    hpoly = hc + np.outer(0.30 * np.sin(th_), v) + np.outer(0.255 * np.cos(th_), pv)
    pen.paint([('p', hpoly)])
    for sd in 'RL':
        arm(sd)


# ====================================================================== utilidades de escena
def draw_bar(pen, y, x0, x1, w=0.05):
    pen.line([(x0, y), (x1, y)], w=pen.c.LW * 1.0, col=INK)


def draw_arrow(pen, center, r, a0, a1, col=GREY_ARROW, w=None):
    """flecha circular (math coords) de a0 a a1 grados"""
    angs = np.linspace(a0, a1, 40)
    pts = np.array([np.asarray(center) + r * dv(a) for a in angs])
    pen.line(pts, w=w or pen.c.LI * 1.1, col=col)
    # punta
    end = pts[-1]; tan = pts[-1] - pts[-3]; tan = tan / (np.linalg.norm(tan) + 1e-9)
    nrm = np.array([-tan[1], tan[0]])
    hl = 0.10
    tip = end + tan * 0.05
    pen.line([tip - tan * hl + nrm * hl * 0.6, tip, tip - tan * hl - nrm * hl * 0.6], w=w or pen.c.LI * 1.1, col=col)


def draw_line_arrow(pen, a, b, col=GREY_ARROW, w=None, both=False):
    a = np.asarray(a, float); b = np.asarray(b, float)
    pen.line([a, b], w=w or pen.c.LI * 1.1, col=col)
    def head(tip, frm):
        t_ = tip - frm; t_ = t_ / (np.linalg.norm(t_) + 1e-9); nr = np.array([-t_[1], t_[0]]); hl = 0.10
        pen.line([tip - t_ * hl + nr * hl * 0.6, tip, tip - t_ * hl - nr * hl * 0.6], w=w or pen.c.LI * 1.1, col=col)
    head(b, a)
    if both:
        head(a, b)


def render_scene(frames, out_base, durations=None, props=None, floor=True, ground_all=True, extras=None, margin=0.5,
                 floor_pad=0.0, y_floor=0.0, bbox_extra=None, quiet=False):
    """frames: lista de dicts de pose ('view': 'side'|'front'). Genera PNG por fotograma y GIF."""
    Js = []
    for fr in frames:
        if fr.get('view', 'side') == 'side':
            J = build_side(fr)
            if fr.get('ground', True):
                J = shift_J(J, ground_shift(J) + fr.get('dy', 0))
            elif 'dy' in fr:
                J = shift_J(J, fr['dy'])
            J['view'] = 'side'
        else:
            J = build_front(fr)
            if fr.get('ground', True):
                J = shift_front(J, front_shift(J) + fr.get('dy', 0))
            elif 'dy' in fr:
                J = shift_front(J, fr['dy'])
            J['view'] = 'front'
        Js.append(J)
    pts = []
    for J in Js:
        pts.append(all_points(J) if J['view'] == 'side' else pts_front(J))
    pts = np.vstack(pts)
    x0, y0 = pts.min(0); x1, y1 = pts.max(0)
    y0 = min(y0 - 0.25, y_floor) if floor else y0 - 0.25
    if props:
        for pr in props:
            if pr[0] == 'bar':
                y1 = max(y1, pr[1] + 0.1); x0 = min(x0, pr[2]); x1 = max(x1, pr[3])
            elif pr[0] == 'box':
                x0 = min(x0, pr[1]); x1 = max(x1, pr[2]); y1 = max(y1, pr[4])
    if bbox_extra:
        x0 = min(x0, bbox_extra[0]); y0 = min(y0, bbox_extra[1]); x1 = max(x1, bbox_extra[2]); y1 = max(y1, bbox_extra[3])
    cv_ = Canvas((x0, y0, x1, y1), margin=margin)
    imgs = []
    for i, J in enumerate(Js):
        img = np.full((CH * SS, CW * SS, 3), 255, np.uint8)
        pen = Pen(cv_, img)
        if floor:
            fy = cv_.C((0, y_floor - 0.055 + floor_pad))[1]
            cv2.line(img, (0, int(fy)), (CW * SS, int(fy)), FLOOR, int(2.4 * SS), cv2.LINE_AA)
        if props:
            for pr in props:
                if pr[0] == 'bar':
                    pen.line([(pr[2], pr[1]), (pr[3], pr[1])], w=cv_.LW * 1.3)
                elif pr[0] == 'post':
                    pen.line([(pr[1], pr[2]), (pr[1], pr[3])], w=cv_.LW * 1.3)
                elif pr[0] == 'floorbar':
                    pen.line([(pr[1], pr[2]), (pr[3], pr[4])], w=cv_.LW * 1.3)
        if J['view'] == 'side':
            draw_side(pen, J)
        else:
            draw_front(pen, J)
        if extras and extras[i]:
            for ex in extras[i]:
                ex(pen)
        imgs.append(cv2.resize(img, (CW, CH), interpolation=cv2.INTER_AREA))
    base = out_base
    for i, im in enumerate(imgs):
        cv2.imwrite(f'{base}_{i + 1}.png', im)
    cv2.imwrite(base + '_par.png', np.hstack(imgs[:4]) if len(imgs) > 1 else imgs[0])
    rgb = [Image.fromarray(cv2.cvtColor(f_, cv2.COLOR_BGR2RGB)) for f_ in imgs]
    mont = Image.new('RGB', (CW, CH * len(rgb)))
    for i, r_ in enumerate(rgb):
        mont.paste(r_, (0, CH * i))
    pal = mont.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pil = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in rgb]
    durs = durations or [1100] * len(pil)
    pil[0].save(base + '.gif', save_all=True, append_images=pil[1:], duration=durs, loop=0, optimize=True, disposal=1)
    if not quiet:
        print('GIF', base + '.gif', os.path.getsize(base + '.gif') // 1024, 'KB', len(pil), 'frames')
    return imgs
