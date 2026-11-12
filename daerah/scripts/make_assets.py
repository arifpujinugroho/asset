"""Buat aset webp seragam dari file asli hasil download_wiki.py:
  lg-<kode>.webp  1920x1920   <kode>.webp  512x512   sm-<kode>.webp  250x250
Semua kanvas persegi contain-fit (aspek asli, padding transparan, tanpa distorsi).
SVG tetap ada .svg-nya dan dirender via thumbnail Wikimedia 1920px (ukuran resmi).
"""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bgfill import bg_fill  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, '.cache-svgrender')
os.makedirs(CACHE, exist_ok=True)
WORKERS = 3
UA = 'DaerahAssetFetcher/1.0 (local asset repository build; contact: repo owner)'
SIZES = {'lg-': 1920, '': 512, 'sm-': 250}


def download_svg_render(kode, url):
    out = os.path.join(CACHE, f'{kode}.png')
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out
    rel = url.replace('https://upload.wikimedia.org/wikipedia/', '')
    parts = rel.split('/')
    thumb = '/'.join(parts[:1] + ['thumb'] + parts[1:]) + '/1920px-' + parts[-1] + '.png'
    full = 'https://upload.wikimedia.org/wikipedia/' + thumb
    for attempt in range(5):
        time.sleep(0.7)
        try:
            import urllib.request
            req = urllib.request.Request(full, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if not data.startswith(b'\x89PNG'):
                raise ValueError('bukan render PNG')
            with open(out, 'wb') as fh:
                fh.write(data)
            return out
        except Exception as e:
            print(f'  render {kode} retry ({str(e)[:80]})', flush=True)
            time.sleep(2 * (attempt + 1) + (28 if '429' in str(e) else 0))
    raise RuntimeError(f'render SVG gagal: {kode}')


def corners_transparent(arr):
    h, w = arr.shape[:2]
    return all(arr[y, x, 3] < 10 for x, y in
               [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])


def prepare_source(j):
    """Sumber berkualitas penuh (PNG RGBA) untuk satu kode."""
    kode, ext = j['kode'], j['ext']
    out = os.path.join(CACHE, f'master-{kode}.png')
    if ext == 'svg':
        render = download_svg_render(kode, j['url'])
        arr = np.array(Image.open(render).convert('RGBA'))
        if not corners_transparent(arr):
            arr, _ = bg_fill(arr, 60, 110)
        Image.fromarray(arr).save(out)
    else:
        subprocess.run(['magick', os.path.join(BASE, f'{kode}.{ext}'), '-background', 'none',
                        'PNG32:' + out], check=True)
    return out


def encode(j):
    kode = j['kode']
    master = prepare_source(j)
    sq = os.path.join(CACHE, f'sq-{kode}.png')
    subprocess.run(['magick', master, '-background', 'none', '-resize', '1920x1920',
                    '-gravity', 'center', '-extent', '1920x1920', 'PNG32:' + sq], check=True)
    r = subprocess.run(['cwebp', '-quiet', '-q', '80', sq, '-o', os.path.join(BASE, f'lg-{kode}.webp')],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'cwebp lg-{kode}: {r.stderr[:120]}')
    for prefix, size in [('sm-', 250), ('', 512)]:
        name = f'{prefix}{kode}.webp'
        resized = os.path.join(CACHE, f'r-{kode}-{size}.png')
        subprocess.run(['magick', sq, '-background', 'none', '-resize', f'{size}x{size}',
                        'PNG32:' + resized], check=True)
        r = subprocess.run(['cwebp', '-quiet', '-q', '80', resized, '-o', os.path.join(BASE, name)],
                           capture_output=True, text=True)
        if r.returncode != 0 or os.path.getsize(os.path.join(BASE, name)) == 0:
            raise RuntimeError(f'cwebp {name}: {r.stderr[:120]}')
    for p in (master, sq, os.path.join(CACHE, f'r-{kode}-250.png'), os.path.join(CACHE, f'r-{kode}-512.png')):
        try:
            os.remove(p)
        except OSError:
            pass
    return kode


def main():
    with open(os.path.join(BASE, 'data', 'wiki_jobs.json')) as f:
        jobs = json.load(f)
    failed = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(encode, j): j for j in jobs}
        for fut in as_completed(futs):
            j = futs[fut]
            try:
                fut.result()
                done += 1
                if done % 50 == 0:
                    print(f'progress {done}/{len(jobs)}', flush=True)
            except Exception as e:
                failed.append((j['kode'], j['uraian'], str(e)[:150]))
                print(f'GAGAL {j["kode"]} {j["uraian"]}: {str(e)[:150]}', flush=True)
    print(f'DONE ok={done} gagal={len(failed)}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
