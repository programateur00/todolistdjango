import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = sys.argv[1] if len(sys.argv) > 1 else './crunch'

def limb_leg_flat(spec, H):
    """Igual que figura.limb_leg, pero con spec[4]=='flat' el pie queda plano con la planta hacia abajo
    aunque apunte a la izquierda (figura.py asume pie a la derecha)."""
    if len(spec) > 4 and spec[4] == 'flat':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        d = dv(spec[3]); p = np.array([0.0, -1.0])
        he = a + p * 0.10 - d * 0.07
        to = he + d * 0.44
        return H, k, a, he, to
    return _orig(spec, H)
_orig = figura.limb_leg
figura.limb_leg = limb_leg_flat

def shin_for(thigh, drop=0.06):
    """Angulo de la espinilla para que gluteo y pie queden en la misma linea de suelo."""
    s = (-drop - L_THIGH * np.sin(np.deg2rad(thigh))) / L_SHIN
    return 360 - np.rad2deg(np.arcsin(s)) - 180 + 180 if False else 180 + np.rad2deg(np.arcsin(-s))

if __name__ == '__main__':
    import json
    cfg = dict(bn='ccw', bf='ccw', du=0.05, dn=-0.28, t1=22, h1=54, t0=2, h0=8, thigh=127, ex=0.0, top=0.60, left=0.0, right=0.12, margin=0.40)
    for a in sys.argv[2:]:
        k, v = a.split('='); cfg[k] = v if k in ('bn', 'bf') else float(v)
    tn, tf = cfg['thigh'], cfg['thigh'] - 6
    legs = dict(near_leg=('fk', tn, shin_for(tn), 180, 'flat'), far_leg=('fk', tf, shin_for(tf), 180, 'flat'))
    arms = dict(near_arm=('ikh', cfg['du'], cfg['dn'], cfg['bn']), far_arm=('ikh', cfg['du'] + 0.03, cfg['dn'] + 0.02, cfg['bf']))
    base = dict(f=-1, hip=(0, 0.3), **legs, **arms)
    frames = [dict(base, torso=cfg['t0'], head=cfg['h0']), dict(base, torso=cfg['t1'], head=cfg['h1'])]
    # cuadro igual que situp12: suelo en y~293, figura ocupando ~x 38..452
    bb = None
    if cfg['top'] or cfg['left'] or cfg['right']:
        pts = []
        for fr in frames + [dict(base, torso=34, head=44)]:  # encuadre fijo (igual que la 1ª versión)
            J = build_side(fr); J = shift_J(J, ground_shift(J)); pts.append(all_points(J))
        pts = np.vstack(pts); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
        bb = (x0 - cfg['left'], min(y0 - 0.25, 0), x1 + cfg['right'], y1 + cfg['top'])
    render_scene(frames, OUT, bbox_extra=bb, margin=cfg['margin'])
