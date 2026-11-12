"""Terapkan skema ukuran yang sama (lg-1920 / 512 / sm-250) ke aset provinsi
(file <kode>.webp dengan kode puluhan yang sudah ada di folder aset).
"""
import glob, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, '.cache-prov')
os.makedirs(TMP, exist_ok=True)
WORKERS = 3


def encode(src):
    kode = os.path.basename(src).split('.')[0]
    sq = os.path.join(TMP, f'{kode}_sq.png')
    subprocess.run(['magick', src, '-background', 'none', '-resize', '1920x1920',
                    '-gravity', 'center', '-extent', '1920x1920', 'PNG32:' + sq], check=True)
    r = subprocess.run(['cwebp', '-quiet', '-q', '80', sq, '-o', os.path.join(BASE, f'lg-{kode}.webp')],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'cwebp lg-{kode}: {r.stderr[:120]}')
    for size, name in [(512, f'{kode}.webp'), (250, f'sm-{kode}.webp')]:
        resized = os.path.join(TMP, f'{kode}_{size}.png')
        subprocess.run(['magick', sq, '-background', 'none', '-resize', f'{size}x{size}',
                        'PNG32:' + resized], check=True)
        r = subprocess.run(['cwebp', '-quiet', '-q', '80', resized, '-o', os.path.join(BASE, name)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'cwebp {name}: {r.stderr[:120]}')
    for p in (sq, os.path.join(TMP, f'{kode}_512.png'), os.path.join(TMP, f'{kode}_250.png')):
        try:
            os.remove(p)
        except OSError:
            pass
    return kode


def main():
    # kode puluhan = nama file yang setelah ekstensi panjangnya <= 6 (mis. 11.webp)
    srcs = [p for p in glob.glob(os.path.join(BASE, '*.webp'))
            if os.path.basename(p).split('.')[0].isdigit() and len(os.path.basename(p).split('.')[0]) == 2]
    print(f'provinsi ditemukan: {len(srcs)}')
    failed = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(encode, s): s for s in srcs}
        for fut in as_completed(futs):
            try:
                print(f'{fut.result()} ok', flush=True)
            except Exception as e:
                failed.append((futs[fut], str(e)[:150]))
                print(f'{futs[fut]} GAGAL: {str(e)[:150]}', flush=True)
    try:
        os.rmdir(TMP)
    except OSError:
        pass
    print(f'DONE gagal={len(failed)}')
    if failed:
        for kode, err in failed:
            print(f'  {kode}: {err}')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
