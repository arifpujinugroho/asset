"""Unduh lambang kabupaten/kota dari Wikipedia + buat aset webp seragam.

Alur:
  1. download_wiki.py  : parse halaman Wikipedia, cocokkan dengan JSON kode,
                         unduh file asli secara serial (rate-limit).
  2. make_assets.py    : buang latar + encode 3 ukuran persegi:
                         lg-<kode>.webp (1920), <kode>.webp (512), sm-<kode>.webp (250).
                         SVG tetap ada file .svg-nya + di-render via Wikimedia 1920px.

Pemakaian:
  python3 -m venv .venv && .venv/bin/pip install pillow numpy
  .venv/bin/python scripts/download_wiki.py
  .venv/bin/python scripts/make_assets.py

Catatan:
  - Unduhan serial ~0.7s/request dengan User-Agent deskripatif sesuai kebijakan
    Wikimedia; thumbnail SVG hanya boleh memakai ukuran resmi (1920 termasuk).
  - Butuh `cwebp` dan `magick` (ImageMagick) di PATH.
  - Provinsi (kode puluhan): make_provinsi.py
"""
