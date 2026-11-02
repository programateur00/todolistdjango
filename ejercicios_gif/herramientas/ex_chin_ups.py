"""Chin ups (dominadas supinas), vista FRONTAL, agarre supino (palmas hacia ti) a la anchura de los hombros.
Mismo montaje (barra + postes), muñeco y vista que ex_dominadas.py (dominadas normales); cambian:
  - agarre estrecho (manos justo encima de los hombros, no mas anchas que ellos),
  - arriba los codos NO se abren: bajan pegados al torso (en la vista frontal el brazo queda "plegado" por
    delante del cuerpo: brazo corto hacia abajo, antebrazo vertical hasta la barra),
  - la barbilla pasa la barra con algo mas de margen (la chin up llega algo mas alto que la dominada prona).
Uso: python ex_chin_ups.py [carpeta_salida] [clave=valor ...]   (genera chin-ups.gif + PNG de cada fotograma)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figura import *

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
BAR = 4.35
RIG = [('bar', BAR, -1.25, 1.25), ('post', -1.25, 0.0, BAR + 0.25), ('post', 1.25, 0.0, BAR + 0.25)]
CFG = dict(grip=0.36, hipA=2.16, top_dy=0.18, head=90, shin=0.55, margin=0.5,
           ua_a=272, fa_a=88, fa_s=0.97)   # arriba: angulos del brazo/antebrazo y escorzo del antebrazo (vista frontal)
for a in sys.argv[2:]:
    k, v = a.split('='); CFG[k] = float(v)

g = CFG['grip']
legs = dict(R_leg=('fk', 272, 272), L_leg=('fk', 268, 268), shin_R=CFG['shin'], shin_L=CFG['shin'])


def pose(hip_y, shrug=0.0, head=90, **kw):
    return dict(view='front', ground=False, hip=(0, hip_y), torso=90, head=head, shrug=shrug, **legs, **kw)


# A: colgado con los brazos (casi) estirados, manos al ancho de los hombros (abajo)
A = pose(CFG['hipA'], R_arm=('ik', (g, BAR), 'cw'), L_arm=('ik', (-g, BAR), 'ccw'))

# B: barbilla por encima de la barra (arriba). Codos pegados al torso: brazo hacia abajo (escorzo) + antebrazo
#    casi vertical hasta la barra. El antebrazo derecho se aleja un pelin del cuerpo, el izquierdo es el espejo.
ua, fa, fas = CFG['ua_a'], CFG['fa_a'], CFG['fa_s']
# escorzo del brazo calculado para que la muñeca quede justo en la barra (la mano agarra la barra aunque cambies top_dy)
uas = (L_FA * fas * np.sin(np.deg2rad(fa)) - CFG['top_dy']) / (-L_UA * np.sin(np.deg2rad(ua)))
B = pose(BAR - CFG['top_dy'] - 1.0, head=CFG['head'],
         R_arm=('fk', ua, fa), L_arm=('fk', (180 - ua) % 360, (180 - fa) % 360),
         fore_R_ua=uas, fore_L_ua=uas, fore_R_fa=fas, fore_L_fa=fas)
render_scene([A, B], OUT + 'chin-ups', props=RIG, durations=[1200, 1200], margin=CFG['margin'])
