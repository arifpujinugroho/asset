"""Flood-fill background removal: buang latar di pinggiran lambang.

Pixel yang terhubung ke tepi gambar dengan warna mirip warna sudut dibuat
transparan; area serupa di dalam lambang tetap utuh. Penghalang dua tingkat
(tol kandidat + strong-barrier yang didilasi) mencegah fill menembus border
tipis maupun border bergaya checkerboard/stipple.
"""
import os, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter


def load_rgba(src):
    out = os.path.join(tempfile.gettempdir(), f'bgfill_{os.getpid()}_{os.getrandbits(32):x}.png')
    subprocess.run(['magick', src, '-background', 'none', 'PNG32:' + out], check=True)
    try:
        return np.array(Image.open(out).convert('RGBA'))
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


def bg_fill(arr, tol=60, strong_tol=110):
    """Transparankan area latar yang terhubung ke tepi. Return (arr, changed)."""
    h, w = arr.shape[:2]
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    opaque_seeds = [arr[y, x, :3].astype(np.int16) for x, y in seeds if arr[y, x, 3] > 200]
    if not opaque_seeds:
        return arr, False
    rgb = arr[:, :, :3].astype(np.int16)
    cand = arr[:, :, 3] > 200
    dist = np.full((h, w), 255, dtype=np.int16)
    for sp in opaque_seeds:
        dist = np.minimum(dist, np.abs(rgb - sp).max(axis=2))
    cand &= dist < tol
    strong = dist >= strong_tol
    for _ in range(1):  # dilasi barrier kuat 1px: melindungi border poros/checkerboard
        p = np.pad(strong, 1, constant_values=False)
        strong = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    cand &= ~strong
    visited = np.zeros((h, w), dtype=bool)
    visited[0, :] = cand[0, :]
    visited[-1, :] |= cand[-1, :]
    visited[:, 0] |= cand[:, 0]
    visited[:, -1] |= cand[:, -1]
    if not visited.any():
        return arr, False
    while True:
        new = visited.copy()
        new[1:, :] |= visited[:-1, :]
        new[:-1, :] |= visited[1:, :]
        new[:, 1:] |= visited[:, :-1]
        new[:, :-1] |= visited[:, 1:]
        new &= cand
        if np.array_equal(new, visited):
            break
        visited = new
    arr = arr.copy()
    arr[:, :, 3][visited] = 0
    return arr, True


def smooth_alpha(arr):
    """Haluskan tepi alpha (untuk sumber JPG yang berartefak kompresi)."""
    im = Image.fromarray(arr)
    a = im.getchannel('A').filter(ImageFilter.GaussianBlur(0.7))
    a = a.point(lambda v: min(255, int(v * 2.0)))
    im.putalpha(a)
    return np.array(im)


def process(src, dst, tol=60, smooth=False, strong_tol=110):
    """Buang latar `src` (format apa pun yang dikenal magick) -> PNG RGBA `dst`."""
    arr = load_rgba(src)
    arr, changed = bg_fill(arr, tol, strong_tol)
    if smooth and changed:
        arr = smooth_alpha(arr)
    Image.fromarray(arr).save(dst)
    return changed
