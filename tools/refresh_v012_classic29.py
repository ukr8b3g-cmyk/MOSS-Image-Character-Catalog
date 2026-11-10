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
BASE_ID = 728700141
SUM_ID = 728700147
BASE_SHA = '3734f42fc167b71c25fa11b63056b880cbffbdfe5898d61accfaec5812b3bbf0'
SUM_SHA = '5c581e197fca0103e2241f3ac737f0802f034867fa0deb8a1fab46935502087e'
PREFIX = 'MOSS-Image-Character-Catalog/'
NAME = 'MOSS-Image-Character-Catalog-v0.1.2.zip'
STAGED_NAME = NAME.replace('.zip', '-classic29.zip')
OLD_NAME = NAME.replace('.zip', '-before-classic29-20261110.zip')
SUM_STAGED = 'SHA256SUMS-classic29.txt'
SUM_OLD = 'SHA256SUMS-before-classic29-20261110.txt'


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
    body += '**Classic Cartoon update / クラシック・カートゥーン追加（2026-11-10）**\n\n'
    body += '34,709 images: 34,395 characters + 314 styles. Added 7 Flintstones + 22 other classic-cartoon characters, excluding 8 duplicate candidates. The independent Classic Cartoon work filter groups relevant works; reusable prompts explicitly include classic cartoon. Images remain uncurated.\n\n'
    body += 'フリントストーン7件＋その他22件を追加。既存候補8件は除外。クラシック・カートゥーン分類とコピー用プロンプトを更新。34,395キャラクター＋314スタイル＝34,709枚。画像は未選別です。\n\n'
    body += 'SFT INT8 ConvRot + LoRA 1.0, 8 steps, CFG1, seed8961184, er_sde/simple, Small Decoder, 896×1184, WebP70.\n\n'
    body += f'7-Zip selective update: {result["unchanged_compressed_entries"]:,} untouched compressed entries preserved. Previous ZIP/checksum retained as before-classic29-20261110.\n\n'
    body += '[Full online demo (read-only)](https://huggingface.co/spaces/hide1/MOSS-Image-Character-Catalog) · [Characters and features](https://github.com/' + REPO + '/blob/main/docs/updates/classic29-20261110.csv)\n\n'
    body += f'SHA256: {result["sha256"]}  {NAME}\n'
    api('releases/' + str(RELEASE_ID), {'body': body, 'name': 'v0.1.2 — 34,709 samples (Classic Cartoon update)'}, output)
    final = api('releases/' + str(RELEASE_ID)); assets = {item['name']: item for item in final['assets']}
    assert assets[NAME]['id'] == new['id'] and assets[NAME]['digest'] == 'sha256:' + result['sha256']
    assert assets['SHA256SUMS.txt']['id'] == new_sum['id']
    for name, old in existing.items():
        preserved = OLD_NAME if name == NAME else SUM_OLD if name == 'SHA256SUMS.txt' else name
        assert assets[preserved]['id'] == old['id'] and assets[preserved]['digest'] == old['digest']
    result['assets'] = {name: {key: item[key] for key in ['id', 'digest', 'size']} for name, item in assets.items()}
    (output / 'publication.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='changed_files'}, indent=2), flush=True)


DELTA_URL = 'https://huggingface.co/datasets/hide1/MOSS-Image-Character-Catalog/resolve/abdea83e2fb9dcb52683c7fdaad748f77512f266/release-updates/20261110/classic29-delta.zip'
DELTA_SHA = '947f2cce827739a896d8a6f5f630c459a9ed7bbe24fd12daf462022071d1da63'
EXPECTED_SHA = '770746780a507fb2ae561b52a5370f6003a5e71587ca4a8a205451bc092def31'
EXPECTED_SIZE = 2088706015

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
