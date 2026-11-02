"""Bicicleta (bicycle crunch), vista de PERFIL, tumbado boca arriba con la cabeza a la DERECHA y los pies a la izquierda, igual que crunch.gif / double-crunch.gif / leg-raise.gif
(mismo muñeco, estilo y suelo: ex_crunch.py / ex_double_crunch.py / figura.py). SIN cara (ni nariz ni ojo ni oreja: figura.draw_side no dibuja cara).
Como lo mira la app: slug bicycle-crunch (migracion 0002), mode "timed", counter_key "" -> NO tiene contador de camara, es una cuenta atras a secas
(circuit.js: «timed sin counter_key (bicicleta…) -> cuenta atras a secas»). Por eso aqui no hay umbrales de workout.js que respetar; solo se comprueba que el dibujo sea coherente.
Tecnica (guias de ACE, WBEZ, Fitbod, Garage Gym Reviews, The Gym Group, MasterClass): tumbado, manos detras de la nuca (sin tirar del cuello), SOLO se despegan los omoplatos
(subir el torso entero es un error comun) y la zona lumbar sigue en el suelo; una rodilla hacia el pecho (espinilla paralela al suelo) mientras la otra pierna queda ESTIRADA a ras de suelo
(unos pocos centimetros; aqui el talon casi lo toca); el torso GIRA y el codo del lado contrario va hacia la rodilla; se alterna de lado.
GIF de 6 fotogramas (pedaleo fluido): extremo A (cercana estirada a ras de suelo, rodilla lejana hacia el pecho, omoplatos despegados y girados) -> 2 fotogramas de paso (las piernas se cruzan,
el torso baja y pasa por el centro) -> extremo B (todo al reves) -> 2 fotogramas de paso de vuelta -> A.
El GIRO del torso se ve en el HOMBRO: de perfil, al girar el hombro de un lado se adelanta hacia el vientre y el del otro se va hacia la espalda (parametro `twist`, desplaza la raiz de cada brazo
a lo largo del vientre), ademas de la cabeza encogida hacia la rodilla.
Uso: python ex_bicicleta.py [carpeta_salida] [clave=valor ...]   (genera bicycle-crunch.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import figura
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
CFG = dict(t_peak=24, h_peak=44, t_dip=6, h_dip=16,
           tuck_th=74, tuck_sh=184, ext_th=179, ext_sh=180, foot_tuck=24, foot_ext=18,
           twist=0.14, du_n=0.05, dn_n=-0.28, du_f=0.08, dn_f=-0.26,
           margin=0.40, dur_peak=800, dur_step=140)
# t_peak/h_peak: inclinacion del torso y angulo de la cabeza en los extremos (solo se despegan los omoplatos, el torso casi tumbado, cabeza levantada hacia la rodilla); t_dip/h_dip: lo mismo en el paso por el centro (los hombros casi vuelven al suelo)
# tuck_*: muslo/espinilla de la pierna doblada (rodilla hacia el pecho, espinilla casi paralela al suelo); ext_*: de la pierna estirada (pie en el suelo); foot_*: cuanto apunta el pie respecto a 90° con la espinilla
# twist: cuanto se adelanta/atrasa cada hombro (unidades de torso) al girar; du_*/dn_*: manos detras de la nuca (como ex_crunch.py) del brazo cercano / lejano
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)


# ---- pie de la pierna: la planta mira "hacia fuera" de la espinilla (figura.limb_leg asume un pie apoyado y apuntando a la derecha), igual que ex_double_crunch.py
def limb_leg_air(spec, H):
    if len(spec) > 4 and spec[4] == 'air':
        k = H + dv(spec[1]) * L_THIGH; a = k + dv(spec[2]) * L_SHIN
        s = dv(spec[2])
        d = rot(s, -90 + spec[3])        # direccion talon -> puntera: perpendicular a la espinilla, hacia el vientre, algo estirada
        p = rot(d, 90)                   # hacia donde mira la planta (hacia fuera de la espinilla)
        he = a + p * 0.10 - d * 0.07
        to = he + d * 0.44
        return H, k, a, he, to
    return _orig(spec, H)


# ---- brazo con la raiz del hombro desplazada a lo largo del vientre (giro del torso visto de perfil): spec = dict(off=..., a=<spec normal>)
def limb_arm_twist(spec, S, hd, bel):
    if isinstance(spec, dict):
        S2 = S + bel * spec['off']
        _, e, w = _orig_arm(spec['a'], S2, hd, bel)
        return S2, e, w
    return _orig_arm(spec, S, hd, bel)


_orig = figura.limb_leg
figura.limb_leg = limb_leg_air
_orig_arm = figura.limb_arm
figura.limb_arm = limb_arm_twist


def lerp(a, b, u):
    return a + (b - a) * u


def pose(u, dip):
    """u = 0: extremo A (cercana estirada, lejana al pecho; el hombro cercano se adelanta); u = 1: extremo B (al reves). dip = 0..1, cuanto baja el torso en el paso."""
    near_th = lerp(CFG['ext_th'], CFG['tuck_th'], u); near_sh = lerp(CFG['ext_sh'], CFG['tuck_sh'], u); near_ft = lerp(CFG['foot_ext'], CFG['foot_tuck'], u)
    far_th = lerp(CFG['tuck_th'], CFG['ext_th'], u); far_sh = lerp(CFG['tuck_sh'], CFG['ext_sh'], u); far_ft = lerp(CFG['foot_tuck'], CFG['foot_ext'], u)
    torso = lerp(CFG['t_peak'], CFG['t_dip'], dip); head = lerp(CFG['h_peak'], CFG['h_dip'], dip)
    tw = CFG['twist'] * (1 - 2 * u)           # +twist (hombro cercano adelante, lejano atras) -> -twist
    return dict(f=-1, hip=(0, 0.3), torso=torso, head=head,
                near_leg=('fk', near_th, near_sh, near_ft, 'air'), far_leg=('fk', far_th, far_sh, far_ft, 'air'),
                near_arm=dict(off=tw, a=('ikh', CFG['du_n'], CFG['dn_n'], 'ccw')),
                far_arm=dict(off=-tw, a=('ikh', CFG['du_f'], CFG['dn_f'], 'ccw')))


#            u     dip
STEPS = [(0.00, 0.00), (0.33, 0.70), (0.67, 0.70), (1.00, 0.00), (0.67, 0.70), (0.33, 0.70)]
FRAMES = [pose(u, d) for u, d in STEPS]
DURS = [int(CFG['dur_peak']) if d == 0 else int(CFG['dur_step']) for u, d in STEPS]

render_scene(FRAMES, OUT + 'bicycle-crunch', durations=DURS, margin=CFG['margin'])


# ---------------------------------------------------------------- comprobacion de coherencia (no hay contador de camara que dicte umbrales)
def final_J(fr):
    J = build_side(fr)
    return shift_J(J, ground_shift(J) + fr.get('dy', 0))


BACK_KNEE_BELOW_HIP_MAX_FACTOR = 0.45
for i, (u, d) in enumerate(STEPS):
    J = final_J(FRAMES[i])
    S, H = J['S'], J['H']
    tilt = float(np.degrees(np.arctan2(abs(S[1] - H[1]), abs(S[0] - H[0]))))
    assert 3 <= tilt <= 32, f'fotograma {i + 1}: el torso debe seguir casi en el suelo (solo se despegan los omoplatos), nunca sentado'
    out = [f"{i + 1} (u={u:.2f}): torso {tilt:.0f}°"]
    for sd in ('near', 'far'):
        _, kn, an, he, to = J[sd + '_leg']
        thigh = float(np.linalg.norm(H - kn))
        below = (H[1] - kn[1]) / thigh                  # (rodilla.y - cadera.y) / muslo (y hacia abajo)
        assert below < BACK_KNEE_BELOW_HIP_MAX_FACTOR, f'fotograma {i + 1}/{sd}: boca arriba, la rodilla no puede quedar por debajo de la cadera'
        assert min(an[1], he[1], to[1]) >= -1e-6, f'fotograma {i + 1}/{sd}: el pie no puede atravesar el suelo'
        out.append(f"{sd}: rodilla sobre cadera {-below:.2f} muslos, talon a {he[1]:.2f}")
    print(' | '.join(out))
# en los extremos una pierna esta estirada con el pie apoyado en el suelo y la otra con la rodilla al pecho (muy por encima de la cadera)
for i, (ext, tck) in ((0, ('near', 'far')), (3, ('far', 'near'))):
    J = final_J(FRAMES[i])
    assert J[ext + '_leg'][3][1] < 0.15, f'fotograma {i + 1}: el pie de la pierna estirada debe quedar en el suelo'
    assert J[tck + '_leg'][1][1] - J['H'][1] > 0.8, f'fotograma {i + 1}: la rodilla de la otra pierna debe quedar bien arriba, hacia el pecho'
print('OK: bicicleta coherente (sin cara; sin contador de camara: timed, counter_key vacio)')
