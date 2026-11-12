"""Unduh file asli lambang dari halaman Wikipedia
https://id.wikipedia.org/wiki/Daftar_lambang_kabupaten_dan_kota_di_Indonesia
sesuai kode di data/ref_kotakab.json. Hasil: <kode>.<ext> di folder aset
dan data/wiki_jobs.json (peta kode -> URL, dipakai make_assets.py).
"""
import json, os, re, sys, time
import urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI_URL = 'https://id.wikipedia.org/wiki/Daftar_lambang_kabupaten_dan_kota_di_Indonesia'
UA = 'DaerahAssetFetcher/1.0 (local asset repository build; contact: repo owner)'
GAP = 0.7  # detik antar request (patuhi rate limit Wikimedia)

ALIAS = {
    'Kota Tanjung Balai': 'Kota Tanjungbalai',
    'Kota Padang Sidempuan': 'Kota Padangsidimpuan',
    'Kota Pagar Alam': 'Kota Pagaralam',
    'Kabupaten Muko Muko': 'Kabupaten Mukomuko',
    'Kota Pangkal Pinang': 'Kota Pangkalpinang',
    'Kota Tanjung Pinang': 'Kota Tanjungpinang',
    'Kabupaten Adm. Kep. Seribu': 'Kabupaten Administrasi Kepulauan Seribu',
    'Kabupaten Gunungkidul': 'Kabupaten Gunung Kidul',
    'Kota Palangkaraya': 'Kota Palangka Raya',
    'Kabupaten Kep. Siau Tagulandang Biaro': 'Kabupaten Kepulauan Siau Tagulandang Biaro',
    'Kabupaten Toli Toli': 'Kabupaten Tolitoli',
    'Kabupaten Tojo Una Una': 'Kabupaten Tojo Una-Una',
    'Kabupaten Pangkajene Dan Kepulauan': 'Kabupaten Pangkajene dan Kepulauan',
    'Kota Bau Bau': 'Kota Baubau',
    'Kabupaten Fak Fak': 'Kabupaten Fakfak',
    'Kota Adm. Jakarta Pusat': 'Kota Administrasi Jakarta Pusat',
    'Kota Adm. Jakarta Utara': 'Kota Administrasi Jakarta Utara',
    'Kota Adm. Jakarta Barat': 'Kota Administrasi Jakarta Barat',
    'Kota Adm. Jakarta Selatan': 'Kota Administrasi Jakarta Selatan',
    'Kota Adm. Jakarta Timur': 'Kota Administrasi Jakarta Timur',
}

MAGIC = {'png': b'\x89PNG', 'gif': b'GIF8', 'jpg': b'\xff\xd8', 'jpeg': b'\xff\xd8',
         'tif': b'II*\x00', 'webp': b'RIFF'}


def normalize(uraian):
    n = uraian.strip()
    if n.startswith('Kab. '):
        n = 'Kabupaten ' + n[5:]
    elif n.startswith('Kab '):
        n = 'Kabupaten ' + n[4:]
    elif n.startswith('KOTA '):
        n = 'Kota ' + n[5:]
    return ALIAS.get(n, n)


def parse_wiki(html):
    entries = {}
    for m in re.finditer(r'<li class="gallerybox".*?</li>', html, re.DOTALL):
        block = m.group(0)
        img = re.search(r'src="//thumb\.wikimedia\.org/wikipedia/([a-z]+)/thumb/([^"?]+)\?', block)
        if img:
            repo, fname = img.group(1), img.group(2)
            rel = repo + '/' + '/'.join(fname.split('/')[:3])  # original = a/ab/Filename.ext
        else:
            img2 = re.search(r'src="//upload\.wikimedia\.org/wikipedia/([a-z]+)/([^"?]+)', block)
            if not img2:
                continue
            rel = img2.group(1) + '/' + img2.group(2)
        art = re.search(r'<div class="gallerytext"[^>]*>.*?href="https://id\.wikipedia\.org/wiki/'
                        r'(Kabupaten_[^"]+|Kota_[^"]+)"', block, re.DOTALL)
        if not art:
            continue
        t = art.group(1).replace('_', ' ')
        if t not in entries:  # kemunculan pertama = lambang terkini (bukan lambang lama)
            entries[t] = rel
    return entries


def fetch(url, binary_magic=None, timeout=90):
    for attempt in range(6):
        time.sleep(GAP)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if binary_magic and not data.startswith(binary_magic):
                raise ValueError('invalid content')
            return data
        except urllib.error.HTTPError as e:
            wait = 30 if e.code == 429 else 2 * (attempt + 1)
            print(f'  {e.code} pada {url[-60:]}, tunggu {wait}s', flush=True)
            time.sleep(wait)
        except Exception as e:
            print(f'  retry ({e})', flush=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'gagal unduh: {url}')


def main():
    with open(os.path.join(BASE, 'data', 'ref_kotakab.json')) as f:
        data = json.load(f)
    req = urllib.request.Request(WIKI_URL, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        html = r.read().decode('utf-8')
    entries = parse_wiki(html)
    print(f'entri galeri Wikipedia: {len(entries)}')

    jobs, unmatched = [], []
    for d in data:
        name = normalize(d['uraian'])
        if name not in entries:
            unmatched.append((d['kode'], d['uraian']))
            continue
        rel = entries[name]
        ext = rel.rsplit('.', 1)[-1].lower()
        url = 'https://upload.wikimedia.org/wikipedia/' + rel
        jobs.append({'kode': d['kode'], 'uraian': d['uraian'], 'wiki': name, 'ext': ext, 'url': url})
    if unmatched:
        print('TIDAK COCOK:', unmatched)
        sys.exit(1)
    with open(os.path.join(BASE, 'data', 'wiki_jobs.json'), 'w') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)

    fails = []
    for i, j in enumerate(jobs, 1):
        path = os.path.join(BASE, f"{j['kode']}.{j['ext']}")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        try:
            data = fetch(url=j['url'], binary_magic=MAGIC.get(j['ext']))
            with open(path, 'wb') as fh:
                fh.write(data)
        except Exception as e:
            fails.append((j['kode'], j['uraian'], str(e)[:120]))
        if i % 25 == 0:
            print(f'progress {i}/{len(jobs)}', flush=True)
    print(f'DONE gagal={len(fails)}')
    for kode, uraian, err in fails:
        print(f'  GAGAL {kode} {uraian}: {err}')
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
