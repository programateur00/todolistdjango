"""Pose a la velocidad nativa del video (30 fps) SOLO en una ventana de tiempo, con z y visibilidad.
Uso: extract2.py video.mp4 modelo.task salida.npz t0 t1
"""
import sys, numpy as np, cv2
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision

VIDEO, MODEL, OUT, T0, T1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
opts = vision.PoseLandmarkerOptions(
    base_options=mpt.BaseOptions(model_asset_path=MODEL, delegate=mpt.BaseOptions.Delegate.CPU),
    running_mode=vision.RunningMode.VIDEO, num_poses=1, output_segmentation_masks=False,
    min_pose_detection_confidence=0.4, min_pose_presence_confidence=0.4, min_tracking_confidence=0.4)
lm = vision.PoseLandmarker.create_from_options(opts)

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
cap.set(cv2.CAP_PROP_POS_MSEC, T0 * 1000)
out, times = [], []
n = 0
while True:
    pos = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
    ok, frame = cap.read()
    if not ok or pos > T1:
        break
    res = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), int(n * 1000 / fps))
    if res.pose_landmarks:
        out.append([[l.x, l.y, l.z, l.visibility] for l in res.pose_landmarks[0]])
    else:
        out.append(np.full((33, 4), np.nan).tolist())
    times.append(pos)
    n += 1
np.savez_compressed(OUT, lm=np.array(out, np.float32), t=np.array(times), W=W, H=H, fps=fps)
print("listo", n, "frames", flush=True)
