"""Hollow body (aguante), vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que v-up.gif / leg-raise.gif / double-crunch.gif
(mismo muñeco, estilo y suelo: ex_v_up.py / ex_leg_raise.py / figura.py) y con las flechas / el reloj grises de superman-hold.gif / l-sit-hold.gif.
SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara, y aqui NO se usa ninguna funcion cara()).
Genera UN GIF: hollow-body-hold.gif (slug hollow-body-hold, mode=timed, counter_key=hollowbodyhold): AGUANTE cronometrado.
  todo en el suelo, brazos sobre la cabeza (flechas grises arriba) -> hollow aguantando (reloj gris) -> hollow (reloj con la manecilla avanzada; `clock=0` quita el reloj).
Como lo mira la app (workout.js: createHollowBodyChecker, constantes HOLLOW_*), de PERFIL con hombro, cadera, rodilla y tobillo del lado mejor visto:
  - angulos sobre la horizontal: torso = cadera->hombro, pierna = cadera->tobillo (+ = por encima de la cadera),
  - REPOSO (se aprende tumbado y quieto): torso entre HOLLOW_REST_TORSO_MIN_DEG (-15) y MAX (18), pierna entre HOLLOW_REST_LEG_MIN_DEG (-25) y MAX (12), rodilla >= HOLLOW_REST_KNEE_MIN_DEG (150),
  - HOLLOW: torso despegado sobre su reposo entre HOLLOW_TORSO_LIFT_DEG (10) y HOLLOW_TORSO_MAX_LIFT_DEG (40) Y pierna despegada entre HOLLOW_LEG_LIFT_DEG (6) y HOLLOW_LEG_MAX_LIFT_DEG (50)
    A LA VEZ, rodilla >= HOLLOW_KNEE_MIN_DEG (150), torso < HOLLOW_SIT_DEG (60); hombro y tobillo a lados opuestos de la cadera,
  - la zona lumbar y los glúteos quedan APOYADOS en el suelo (forma de plátano); piernas rectas y juntas, brazos estirados sobre la cabeza.
Al final se comprueban los umbrales del contador contra la geometria dibujada (assert).
Uso: python ex_hollow_body.py [carpeta_salida] [clave=valor ...]   (genera hollow-body-hold.gif + PNG de cada fotograma: usar una carpeta temporal, no ejercicios_gif)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t0=3, h0=9, t1=23, h1=26,                 # torso / cabeza abajo y en el hollow (grados sobre la horizontal)
           th0=181, sh0=182, th1=158, sh1=158,        # muslo / espinilla (grados matematicos; 180 = hacia la izquierda, <180 sube)
           far0=-1.5, far1=3.5, foot0=18, foot1=24,   # grados de mas de la pierna lejana y flexion plantar
           ph0=14, ph1=30, r=1.16, fr=-0.04, fph=3,   # brazos (rectos): direccion hombro->muneca abajo / en el hollow; fph = grados de mas del brazo lejano (r/fr ya no se usan)
           margin=0.40, arrows=1, clock=1, clock_x=0.0, clock_y=1.5, clock_r=0.27,
           arr_len=0.42, arr_gap=0.28, dur0=1300, dur1=1400)
# ph0/ph1: direccion (grados matematicos) del brazo cercano: estirado sobre la cabeza (un poco levantado para no tapar la cabeza, como v-up.gif)
# clock_*, arr_*: posicion del reloj gris y de las flechas
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

# mismos umbrales que workout.js (createHollowBodyChecker)
HOLLOW_REST_TORSO_MAX_DEG = 18
HOLLOW_REST_TORSO_MIN_DEG = -15
HOLLOW_REST_LEG_MAX_DEG = 12
HOLLOW_REST_LEG_MIN_DEG = -25
HOLLOW_REST_KNEE_MIN_DEG = 150
HOLLOW_TORSO_LIFT_DEG = 10
HOLLOW_TORSO_MAX_LIFT_DEG = 40
HOLLOW_LEG_LIFT_DEG = 6
HOLLOW_LEG_MAX_LIFT_DEG = 50
HOLLOW_KNEE_MIN_DEG = 150
HOLLOW_SIT_DEG = 60


# ---- pie "en el aire": la planta mira hacia fuera de la espinilla (igual que ex_v_up.py / ex_leg_raise.py)
def limb_leg_air(spec, H):
    if len(spec) > 4 and spec[4] == 'air':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        s = dv(spec[2])
        d = rot(s, -90 + spec[3])        # direccion talon -> puntera: perpendicular a la espinilla, hacia la cabeza, algo estirada
        p = rot(d, 90)                   # hacia donde mira la planta (hacia fuera de la espinilla)
        he = a + p * 0.10 - d * 0.07
        to = he + d * 0.44
        return H, k, a, he, to
    return _orig(spec, H)


_orig = figura.limb_leg
figura.limb_leg = limb_leg_air


def arm_spec(phi, r=None, bend='ccw'):
    return ('fk', phi, phi)              # brazo ESTIRADO del todo (hombro-codo-muñeca en linea) apuntando en la direccion phi


def pose(t, h, th, sh, far, foot, phi):
    return dict(f=-1, hip=(0, 0.3), torso=t, head=h,
                near_leg=('fk', th, sh, foot, 'air'), far_leg=('fk', th + far, sh + far, foot, 'air'),
                near_arm=arm_spec(phi, CFG['r']), far_arm=arm_spec(phi + CFG['fph'], CFG['r'] + CFG['fr']))


R = pose(CFG['t0'], CFG['h0'], CFG['th0'], CFG['sh0'], CFG['far0'], CFG['foot0'], CFG['ph0'])
U = pose(CFG['t1'], CFG['h1'], CFG['th1'], CFG['sh1'], CFG['far1'], CFG['foot1'], CFG['ph1'])


def final_J(fr):
    J = build_side(fr)
    return shift_J(J, ground_shift(J) + fr.get('dy', 0))


JR, JU = final_J(R), final_J(U)


# ---------------------------------------------------------------- extras: flechas grises y reloj
def flechas(J):
    """dos flechas verticales grises hacia ARRIBA: una sobre hombros/brazos/cabeza y otra sobre las piernas (se despegan a la vez)"""
    def f(pen):
        if not CFG['arrows']:
            return
        L_, g = CFG['arr_len'], CFG['arr_gap']
        xs = (J['S'][0] + 0.15, J['near_leg'][2][0] - 0.05)
        ys = (max(J['hd'][1] + 0.27, J['near_arm'][2][1]), J['near_leg'][2][1] + 0.12)
        for x, ytop in zip(xs, ys):
            draw_line_arrow(pen, (x, ytop + g), (x, ytop + g + L_))
    return f


def reloj(hand_deg):
    """reloj gris encima del cuerpo (aguante cronometrado): esfera + manecilla larga + corta fija"""
    def draw(pen):
        if not CFG['clock']:
            return
        c = np.array([CFG['clock_x'], CFG['clock_y']]); r = CFG['clock_r']
        th = np.linspace(0, 2 * np.pi, 48)
        pen.line(np.array([c + r * np.array([np.cos(t), np.sin(t)]) for t in th]), w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(hand_deg) * r * 0.78], w=pen.c.LI * 1.1, col=GREY_ARROW)
        pen.line([c, c + dv(215) * r * 0.5], w=pen.c.LI * 1.1, col=GREY_ARROW)
    return draw


allp = np.vstack([all_points(JR), all_points(JU)])
bb = (allp[:, 0].min() - 0.1, 0.0, allp[:, 0].max() + 0.1, CFG['clock_y'] + CFG['clock_r'] + 0.1)
render_scene([R, U, U], OUT + 'hollow-body-hold', durations=[int(CFG['dur0']), int(CFG['dur1']), int(CFG['dur1'])], margin=CFG['margin'],
             bbox_extra=bb, extras=[[flechas(JR)], [reloj(90)], [reloj(-10)]])


# ---------------------------------------------------------------- comprobacion contra los umbrales de workout.js (createHollowBodyChecker)
def angle3(a, b, c):
    """angulo en b (grados) entre b->a y b->c, como hollowJointDeg de la app"""
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))))


def medidas(J, sd):
    """torso / pierna: atan2(altura, |dx|) del segmento cadera->hombro y cadera->tobillo (y aqui hacia ARRIBA = + sobre la cadera, como en la app)"""
    S, H = J['S'], J['H']
    hp, kn, an = J[sd + '_leg'][:3]
    torso = float(np.degrees(np.arctan2(S[1] - H[1], abs(S[0] - H[0]))))
    leg = float(np.degrees(np.arctan2(an[1] - H[1], abs(an[0] - H[0]))))
    s, e, w_ = J[sd + '_arm']
    return dict(torso=torso, leg=leg, knee=angle3(H, kn, an), elbow=angle3(s, e, w_), opposite=(S[0] - H[0]) * (an[0] - H[0]) < 0)


def lowest(J):
    ys = [J['H'][1] - 0.20, J['S'][1] - 0.15, J['hd'][1] - 0.27]
    for sd in ('near', 'far'):
        hp, k, a, he, to = J[sd + '_leg']; ys += [a[1] - 0.07, he[1] - 0.04, to[1] - 0.04]
        sh, e, w_ = J[sd + '_arm']; ys += [e[1] - 0.095, w_[1] - 0.09]
    return min(ys)


for sd in ('near', 'far'):
    m0, m1 = medidas(JR, sd), medidas(JU, sd)
    tl, ll = m1['torso'] - m0['torso'], m1['leg'] - m0['leg']       # app: torsoLift / legLift sobre el reposo aprendido
    print(f"{sd:4s} reposo: torso {m0['torso']:+.0f}° pierna {m0['leg']:+.0f}° rodilla {m0['knee']:.0f}° codo {m0['elbow']:.0f}° | "
          f"hollow: torso {m1['torso']:.0f}° pierna {m1['leg']:.0f}° rodilla {m1['knee']:.0f}° codo {m1['elbow']:.0f}° -> sube_torso {tl:+.0f}° sube_pierna {ll:+.0f}°")
    # reposo: tumbado, estirado y quieto (para aprender el reposo)
    assert HOLLOW_REST_TORSO_MIN_DEG <= m0['torso'] <= HOLLOW_REST_TORSO_MAX_DEG, 'reposo: torso plano'
    assert HOLLOW_REST_LEG_MIN_DEG <= m0['leg'] <= HOLLOW_REST_LEG_MAX_DEG, 'reposo: piernas planas'
    assert m0['knee'] >= HOLLOW_REST_KNEE_MIN_DEG, 'reposo: piernas estiradas'
    # hollow: torso Y piernas despegados a la vez (con margen sobre el umbral y sin pasarse), rodillas estiradas, sin incorporarse
    assert HOLLOW_TORSO_LIFT_DEG * 1.5 <= tl <= HOLLOW_TORSO_MAX_LIFT_DEG * 0.7, 'hollow: torso despegado con margen y sin incorporarse'
    assert HOLLOW_LEG_LIFT_DEG * 1.5 <= ll <= HOLLOW_LEG_MAX_LIFT_DEG * 0.7, 'hollow: piernas despegadas con margen y no en V'
    assert m1['knee'] >= max(HOLLOW_KNEE_MIN_DEG, 170), 'hollow: piernas rectas'
    assert m1['torso'] < HOLLOW_SIT_DEG and m1['opposite'] and m0['opposite'], 'de perfil, sin sentarse'
    assert m0['elbow'] >= 170 and m1['elbow'] >= 170, 'brazos estirados'
print(f"punto mas bajo del muñeco: reposo y={lowest(JR):+.2f}, hollow y={lowest(JU):+.2f} (el suelo esta en y=0)")
assert lowest(JR) >= -0.07 and lowest(JU) >= -0.07, 'el muñeco no se hunde en el suelo'
# lumbar apoyada: la cadera (centro) queda a la misma altura que en reposo = apoyada
assert abs(JU['H'][1] - JR['H'][1]) < 0.05, 'la cadera / zona lumbar se queda apoyada en el suelo'
print('OK: el hollow body coincide con los umbrales del contador (hollowbodyhold, createHollowBodyChecker)')
