import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import cv2
import numpy as np
import torch
from tqdm import tqdm

from .config import WAV2LIP_DIR, CHECKPOINT_PATH

_model = None
_detector = None
_device = None
_lock = threading.Lock()

_MEL_STEP_SIZE = 16
_IMG_SIZE = 96


def _get_device() -> str:
    global _device
    if _device is None:
        if torch.cuda.is_available():
            _device = "cuda"
        elif torch.backends.mps.is_available():
            _device = "mps"
        else:
            _device = "cpu"
    return _device


def _ensure_path():
    w2l = str(WAV2LIP_DIR)
    if w2l not in sys.path:
        sys.path.insert(0, w2l)


def _get_model():
    global _model
    if _model is not None:
        return _model
    _ensure_path()
    from models import Wav2Lip

    device = _get_device()
    ckpt = torch.load(str(CHECKPOINT_PATH), map_location=device)
    s = {k.replace("module.", ""): v for k, v in ckpt["state_dict"].items()}
    model = Wav2Lip()
    model.load_state_dict(s)
    _model = model.to(device).eval()
    print(f"Wav2Lip model loaded on {device}")
    return _model


def _get_detector():
    global _detector
    if _detector is not None:
        return _detector
    _ensure_path()
    import face_detection

    _detector = face_detection.FaceAlignment(
        face_detection.LandmarksType._2D,
        flip_input=False,
        device=_get_device(),
    )
    print(f"Face detector loaded on {_get_device()}")
    return _detector


def _smoothen_boxes(boxes: np.ndarray, T: int = 5) -> np.ndarray:
    for i in range(len(boxes)):
        if i + T > len(boxes):
            window = boxes[len(boxes) - T :]
        else:
            window = boxes[i : i + T]
        boxes[i] = np.mean(window, axis=0)
    return boxes


def _detect_faces(
    images: list,
    pads: tuple,
    batch_size: int,
    nosmooth: bool,
) -> list:
    detector = _get_detector()
    pady1, pady2, padx1, padx2 = pads

    while True:
        predictions = []
        try:
            for i in range(0, len(images), batch_size):
                predictions.extend(
                    detector.get_detections_for_batch(np.array(images[i : i + batch_size]))
                )
        except RuntimeError:
            if batch_size == 1:
                raise RuntimeError("Image too big for face detection. Use resize_factor.")
            batch_size //= 2
            print(f"OOM in face detection — new batch size: {batch_size}")
            continue
        break

    results = []
    for rect, image in zip(predictions, images):
        if rect is None:
            raise ValueError("Face not detected in a frame.")
        y1 = max(0, rect[1] - pady1)
        y2 = min(image.shape[0], rect[3] + pady2)
        x1 = max(0, rect[0] - padx1)
        x2 = min(image.shape[1], rect[2] + padx2)
        results.append([x1, y1, x2, y2])

    boxes = np.array(results)
    if not nosmooth:
        boxes = _smoothen_boxes(boxes)
    return [[img[y1:y2, x1:x2], (y1, y2, x1, x2)] for img, (x1, y1, x2, y2) in zip(images, boxes)]


def _build_face_det_results(
    frames: list,
    pads: tuple,
    face_det_batch_size: int,
    nosmooth: bool,
    static: bool,
) -> list:
    if static:
        return _detect_faces([frames[0]], pads, face_det_batch_size, nosmooth)

    n = len(frames)
    stride = max(1, n // 50)
    sample_idx = list(range(0, n, stride))
    sample_results = _detect_faces(
        [frames[i] for i in sample_idx], pads, face_det_batch_size, nosmooth
    )

    results = [None] * n
    for k, i in enumerate(sample_idx):
        results[i] = sample_results[k]
    for i in range(n):
        if results[i] is None:
            nearest = min(range(len(sample_idx)), key=lambda k: abs(sample_idx[k] - i))
            _, (y1, y2, x1, x2) = sample_results[nearest]
            results[i] = [frames[i][y1:y2, x1:x2], (y1, y2, x1, x2)]
    return results


def _datagen(frames, mels, face_det_results, wav2lip_batch_size, static):
    img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []
    for i, m in enumerate(mels):
        idx = 0 if static else i % len(frames)
        face, coords = face_det_results[idx]
        img_batch.append(cv2.resize(face.copy(), (_IMG_SIZE, _IMG_SIZE)))
        mel_batch.append(m)
        frame_batch.append(frames[idx].copy())
        coords_batch.append(coords)

        if len(img_batch) >= wav2lip_batch_size:
            yield _make_batch(img_batch, mel_batch, frame_batch, coords_batch)
            img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []

    if img_batch:
        yield _make_batch(img_batch, mel_batch, frame_batch, coords_batch)


def _make_batch(img_batch, mel_batch, frame_batch, coords_batch):
    imgs = np.asarray(img_batch)
    mels = np.asarray(mel_batch)
    masked = imgs.copy()
    masked[:, _IMG_SIZE // 2 :] = 0
    imgs = np.concatenate((masked, imgs), axis=3) / 255.0
    mels = mels.reshape(len(mels), mels.shape[1], mels.shape[2], 1)
    return imgs, mels, frame_batch, coords_batch


def run_lipsync(
    face: Path,
    audio_path: Path,
    output: Path,
    pads: tuple = (0, 10, 0, 0),
    resize_factor: int = 1,
    nosmooth: bool = False,
    wav2lip_batch_size: int = 128,
    face_det_batch_size: int = 16,
) -> dict:
    _ensure_path()
    import audio as audio_mod

    ext = face.suffix.lower().lstrip(".")
    static = ext in ("jpg", "jpeg", "png")

    if static:
        full_frames = [cv2.imread(str(face))]
        fps = 25.0
    else:
        cap = cv2.VideoCapture(str(face))
        fps = cap.get(cv2.CAP_PROP_FPS)
        full_frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if resize_factor > 1:
                frame = cv2.resize(
                    frame, (frame.shape[1] // resize_factor, frame.shape[0] // resize_factor)
                )
            full_frames.append(frame)
        cap.release()

    print(f"Wav2Lip: {len(full_frames)} frames at {fps:.1f}fps")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        wav_path = tmp / "temp.wav"

        if audio_path.suffix.lower() != ".wav":
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_path), "-strict", "-2", str(wav_path)],
                check=True,
            )
        else:
            wav_path = audio_path

        wav = audio_mod.load_wav(str(wav_path), 16000)
        mel = audio_mod.melspectrogram(wav)

        if np.isnan(mel.reshape(-1)).sum() > 0:
            return {"status": "failed", "error": "Mel contains NaN — add small epsilon noise to wav."}

        mel_chunks = []
        mel_idx_mul = 80.0 / fps
        i = 0
        while True:
            start = int(i * mel_idx_mul)
            if start + _MEL_STEP_SIZE > len(mel[0]):
                mel_chunks.append(mel[:, len(mel[0]) - _MEL_STEP_SIZE :])
                break
            mel_chunks.append(mel[:, start : start + _MEL_STEP_SIZE])
            i += 1

        full_frames = full_frames[: len(mel_chunks)]

        with _lock:
            model = _get_model()
            face_det_results = _build_face_det_results(
                full_frames, pads, face_det_batch_size, nosmooth, static
            )

            device = _get_device()
            frame_h, frame_w = full_frames[0].shape[:2]
            avi_path = tmp / "result.avi"
            writer = cv2.VideoWriter(
                str(avi_path), cv2.VideoWriter_fourcc(*"DIVX"), fps, (frame_w, frame_h)
            )

            gen = _datagen(full_frames, mel_chunks, face_det_results, wav2lip_batch_size, static)
            n_batches = int(np.ceil(len(mel_chunks) / wav2lip_batch_size))
            for imgs, mels_b, frames, coords in tqdm(gen, total=n_batches, desc="Wav2Lip"):
                img_t = torch.FloatTensor(np.transpose(imgs, (0, 3, 1, 2))).to(device)
                mel_t = torch.FloatTensor(np.transpose(mels_b, (0, 3, 1, 2))).to(device)
                with torch.no_grad():
                    pred = model(mel_t, img_t)
                pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0
                for p, f, c in zip(pred, frames, coords):
                    y1, y2, x1, x2 = c
                    p = cv2.resize(p.astype(np.uint8), (x2 - x1, y2 - y1))
                    f[y1:y2, x1:x2] = p
                    writer.write(f)

            writer.release()

        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(audio_path), "-i", str(avi_path),
                "-strict", "-2", "-q:v", "1", str(output),
            ],
            check=True,
        )

    return {"status": "completed"}
