"""7-Zip-only selective update; verify all images and preserve old Release assets."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zipfile
import urllib.request



ROOT = Path(__file__).resolve().parents[1]
REPO = 'ukr8b3g-cmyk/MOSS-Image-Character-Catalog'
RELEASE_ID = 421022122
BASE_ID = 709769425
SUM_ID = 709769424
BASE_SHA = 'bf9718cf25e8e145925809bdd5a76865c7b0dde3cccfd04c08ec031ad8ca8d99'
SUM_SHA = '80357b0aadfe05342b1983d0ecc2b0a0e2074dd463437d16452bb7295d9b98be'
PREFIX = 'MOSS-Image-Character-Catalog/'
NAME = 'MOSS-Image-Character-Catalog-v0.1.2.zip'
STAGED_NAME = NAME.replace('.zip', '-film-tv432.zip')
OLD_NAME = NAME.replace('.zip', '-before-film-tv432-20261110.zip')
SUM_STAGED = 'SHA256SUMS-film-tv432.txt'
SUM_OLD = 'SHA256SUMS-before-film-tv432-20261110.txt'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def gh(*args):
    result = subprocess.run(['gh', *args], check=True, capture_output=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def api(path, body=None, output=None):
    command = ['api', 'repos/' + REPO + '/' + path]
    if body is not None:
        request = output / 'api-request.json'; request.write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')
        command += ['--method', 'PATCH', '--input', str(request)]
    return gh(*command)


def publish(output, target, sums, result):
    release = api('releases/' + str(RELEASE_ID))
    assert release['tag_name'] == 'v0.1.2' and not release['draft'] and not release.get('immutable')
    existing = {item['name']: item for item in release['assets']}
    assert existing[NAME]['id'] == BASE_ID and existing[NAME]['digest'] == 'sha256:' + BASE_SHA
    assert existing['SHA256SUMS.txt']['id'] == SUM_ID and existing['SHA256SUMS.txt']['digest'] == 'sha256:' + SUM_SHA
    assert not set(existing).intersection({STAGED_NAME, SUM_STAGED, OLD_NAME, SUM_OLD})
    subprocess.run(['gh', 'release', 'upload', 'v0.1.2', str(target), str(sums), '--repo', REPO], check=True)
    staged = {item['name']: item for item in api('releases/' + str(RELEASE_ID))['assets']}
    new = staged[STAGED_NAME]; new_sum = staged[SUM_STAGED]
    assert new['digest'] == 'sha256:' + result['sha256'] and new['size'] == result['size']
    assert new_sum['digest'] == 'sha256:' + digest(sums)
    # Only after both uploads are verified, preserve and rename the old pair.
    try:
        api('releases/assets/' + str(BASE_ID), {'name': OLD_NAME}, output)
        api('releases/assets/' + str(SUM_ID), {'name': SUM_OLD}, output)
        api('releases/assets/' + str(new['id']), {'name': NAME}, output)
        api('releases/assets/' + str(new_sum['id']), {'name': 'SHA256SUMS.txt'}, output)
    except Exception:
        # Restore the canonical old pair if promotion is only partly complete.
        current = {item['id']: item for item in api('releases/' + str(RELEASE_ID))['assets']}
        for item, temp_name in [(new, STAGED_NAME), (new_sum, SUM_STAGED)]:
            if current[item['id']]['name'] in {NAME, 'SHA256SUMS.txt'}:
                api('releases/assets/' + str(item['id']), {'name': temp_name}, output)
        api('releases/assets/' + str(BASE_ID), {'name': NAME}, output)
        api('releases/assets/' + str(SUM_ID), {'name': 'SHA256SUMS.txt'}, output)
        raise
    url = 'https://github.com/' + REPO + '/releases/download/v0.1.2/'
    body = f'**[全件版ZIPをダウンロード / Download the complete ZIP]({url}{NAME})** — {result["size"]:,} bytes\n\n'
    body += f'[SHA256SUMS.txt]({url}SHA256SUMS.txt) · [日本語README](https://github.com/{REPO}/blob/main/README.ja.md) · [English README](https://github.com/{REPO}/blob/main/README.md)\n\n'
    body += '**432 additional character samples / キャラクター432枚追加（2026-11-10）**\n\n'
    body += '34,680 images: 34,366 characters + 314 styles. Added 432 samples, removed one actor-unspecified legacy Luke. Films / TV Series are independent filters. Includes Hong Kong films, MAD MAX and two anime characters. Images remain uncurated.\n\n'
    body += 'キャラクター34,366枚＋スタイル314枚＝合計34,680枚。432枚追加、旧ルーク1枚削除。映画・海外ドラマを独立分類し、実際の生成プロンプトも表示します。画像は未選別です。\n\n'
    body += 'New samples: SFT INT8 ConvRot + LoRA 1.0, 8 steps, CFG 1.0, Small Decoder, er_sde/simple, seed 8961184, 896×1184, WebP quality 70.\n\n'
    body += f'7-Zip selective update: {result["unchanged_compressed_entries"]:,} untouched compressed entries preserved. Previous ZIP/checksum retained as before-film-tv432-20261110.\n\n'
    body += '[Full online demo (read-only)](https://huggingface.co/spaces/hide1/MOSS-Image-Character-Catalog)\n\n'
    body += f'SHA256: {result["sha256"]}  {NAME}\n'
    api('releases/' + str(RELEASE_ID), {'body': body, 'name': 'v0.1.2 — 34,680 samples (432 additional characters)'}, output)
    final = api('releases/' + str(RELEASE_ID)); assets = {item['name']: item for item in final['assets']}
    assert assets[NAME]['id'] == new['id'] and assets[NAME]['digest'] == 'sha256:' + result['sha256']
    assert assets['SHA256SUMS.txt']['id'] == new_sum['id']
    for name, old in existing.items():
        preserved = OLD_NAME if name == NAME else SUM_OLD if name == 'SHA256SUMS.txt' else name
        assert assets[preserved]['id'] == old['id'] and assets[preserved]['digest'] == old['digest']
    result['assets'] = {name: {key: item[key] for key in ['id', 'digest', 'size']} for name, item in assets.items()}
    (output / 'publication.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='changed_files'}, indent=2), flush=True)


DELTA_URL='https://huggingface.co/datasets/hide1/MOSS-Image-Character-Catalog/resolve/85f0a7b07789d356061e71bf4e2da45e8a2dfc14/release-updates/20261110/release-delta.zip'
DELTA_SHA='ee17226f713fa1ae02605a26b7a5324008e001f3433f6c4f505a6eb06142535f'
EXPECTED_SHA='83ceb3094694000827f7fef902c7ba7a4b9ea823d47371496112522c9075185f'
EXPECTED_SIZE=2087153954

def rebuild(output):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF')=='refs/heads/main'
    output.mkdir(parents=True,exist_ok=True);base=output/'baseline.zip'
    with base.open('xb') as f:subprocess.run(['gh','api','repos/'+REPO+'/releases/assets/'+str(BASE_ID),'-H','Accept: application/octet-stream'],stdout=f,check=True,timeout=900)
    assert digest(base)==BASE_SHA
    delta=output/'release-delta.zip'
    with urllib.request.urlopen(DELTA_URL,timeout=300) as response,delta.open('xb') as f:shutil.copyfileobj(response,f)
    assert digest(delta)==DELTA_SHA
    with zipfile.ZipFile(delta) as z:
        assert set(z.namelist())=={'plan.json','payload.bin','verification.json'}
        plan=json.loads(z.read('plan.json'));result=json.loads(z.read('verification.json'));payload=output/'payload.bin'
        with z.open('payload.bin') as f,payload.open('xb') as o:shutil.copyfileobj(f,o)
    assert digest(payload)==plan['payload_sha256'] and plan['base_sha256']==BASE_SHA
    assert plan['target_sha256']==EXPECTED_SHA==result['sha256']
    assert plan['target_size']==EXPECTED_SIZE==result['size']<2147483648
    assert sum(s['length'] for s in plan['segments'])==EXPECTED_SIZE
    target=output/STAGED_NAME
    with base.open('rb') as a,payload.open('rb') as b,target.open('xb') as o:
        for s in plan['segments']:
            assert s['source'] in ['base','payload']
            f=a if s['source']=='base' else b
            limit=base.stat().st_size if s['source']=='base' else payload.stat().st_size
            offset=s['offset'];n=s['length'];assert 0<=offset<=limit and 0<n<=limit-offset;f.seek(offset)
            while n:
                chunk=f.read(min(8*1024*1024,n));assert chunk;o.write(chunk);n-=len(chunk)
    assert target.stat().st_size==EXPECTED_SIZE and digest(target)==EXPECTED_SHA
    subprocess.run(['7z','t',str(target)],check=True)
    sums=output/SUM_STAGED;sums.write_bytes((EXPECTED_SHA+'  '+NAME+'\n').encode('ascii'))
    assert sums.read_bytes()==(ROOT/'SHA256SUMS.txt').read_bytes()
    (output/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    publish(output,target,sums,result)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    rebuild(parser.parse_args().output)
