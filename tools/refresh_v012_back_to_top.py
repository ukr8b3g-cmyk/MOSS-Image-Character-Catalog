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



ROOT = Path(__file__).resolve().parents[1]
REPO = 'ukr8b3g-cmyk/MOSS-Image-Character-Catalog'
RELEASE_ID = 421022122
BASE_ID = 694912226
SUM_ID = 694912227
BASE_SHA = '6ae1be213eaa261a3bfd41ba060f7f55c947f3db0daac5df702b90727105dd40'
SUM_SHA = '46a89458c6fb56dc4889b5128fd2c4606f2b7beb549156a81267fff62f95f6bc'
PREFIX = 'MOSS-Image-Character-Catalog/'
NAME = 'MOSS-Image-Character-Catalog-v0.1.2.zip'
STAGED_NAME = NAME.replace('.zip', '-back-to-top.zip')
OLD_NAME = NAME.replace('.zip', '-before-back-to-top.zip')
SUM_STAGED = 'SHA256SUMS-back-to-top.txt'
SUM_OLD = 'SHA256SUMS-before-back-to-top.txt'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def compressed_digest(stream, info):
    stream.seek(info.header_offset)
    header = stream.read(30)
    if header[:4] != b'PK\x03\x04':
        raise ValueError('Unexpected ZIP local header')
    name_size, extra_size = struct.unpack_from('<HH', header, 26)
    stream.seek(name_size + extra_size, 1)
    remaining = info.compress_size
    h = hashlib.sha256()
    while remaining:
        chunk = stream.read(min(remaining, 1024 * 1024))
        if not chunk:
            raise ValueError('Truncated ZIP payload')
        h.update(chunk); remaining -= len(chunk)
    return h.digest()


def build(base, output, sevenzip):
    from back_to_top import transform
    assert digest(base)==BASE_SHA
    output.mkdir(parents=True,exist_ok=True);target=output/STAGED_NAME;assert not target.exists()
    with zipfile.ZipFile(base) as old:
        js,css=transform(old.read(PREFIX+'app/review/review.js').decode('utf-8').replace('\r\n','\n'),old.read(PREFIX+'app/review/review.css').decode('utf-8').replace('\r\n','\n'))
        replacements={'app/review/review.js':js.encode('utf-8'),'app/review/review.css':css.encode('utf-8')}
        records=json.loads(old.read(PREFIX+'app/outputs/user_catalog.json'))['items'];assert len(records)==34249
        assert PREFIX+'SHA256SUMS.txt' not in old.namelist()
    for name in ('README.md','README.ja.md','docs/updates/back-to-top.md'):replacements[name]=(ROOT/name).read_bytes()
    stage=output/'stage'
    for name,blob in replacements.items():
        p=stage/PREFIX/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob)
    subprocess.run(['node','--check',str(stage/PREFIX/'app/review/review.js')],check=True)
    shutil.copy2(base,target)
    listing=output/'update-files.txt';listing.write_text('\n'.join(PREFIX+n for n in replacements)+'\n','utf-8')
    subprocess.run([sevenzip,'u','-tzip','-mm=Deflate','-mx=5','-scsUTF-8','-up1q1r2x2y2z2w2',str(target),'@'+str(listing)],cwd=stage,check=True)
    subprocess.run([sevenzip,'t',str(target)],check=True)
    with zipfile.ZipFile(base) as old,zipfile.ZipFile(target) as new,base.open('rb') as af,target.open('rb') as bf:
        a={i.filename:i for i in old.infolist()};b={i.filename:i for i in new.infolist()}
        assert len(b)==len(new.infolist()) and set(b)==set(a)|{PREFIX+n for n in replacements}
        unchanged=0
        for name,info in b.items():
            relative=name.removeprefix(PREFIX)
            if relative in replacements:assert new.read(name)==replacements[relative]
            else:
                prior=a[name];assert (info.CRC,info.file_size,info.compress_size,info.compress_type)==(prior.CRC,prior.file_size,prior.compress_size,prior.compress_type)
                assert compressed_digest(af,prior)==compressed_digest(bf,info);unchanged+=1
        for row in records:assert hashlib.sha256(new.read(PREFIX+'app/outputs/'+row['files']['image'])).hexdigest()==row['image_sha256']
    checksum=digest(target);sums=output/SUM_STAGED;sums.write_text(checksum+'  '+NAME+'\n','ascii')
    result={'source_sha256':BASE_SHA,'sha256':checksum,'size':target.stat().st_size,'entries':len(b),'unchanged_compressed_entries':unchanged,'images_verified':34249,'characters':33935,'styles':314,'changed_files':list(replacements),'catalog_prompts_and_review_data_unchanged':True}
    (output/'verification.json').write_text(json.dumps(result,indent=2),'utf-8')
    return target,sums,result


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
    body += (ROOT/'docs/updates/back-to-top.md').read_text('utf-8')
    body += f'\n\n34,249 images: 33,935 characters + 314 styles. All remaining image SHA256 values and {result["unchanged_compressed_entries"]:,} untouched compressed payloads verified. Previous ZIP/checksum retained as before-back-to-top.\n\n```text\n{result["sha256"]}  {NAME}\n```\n'
    api('releases/' + str(RELEASE_ID), {'body': body}, output)
    final = api('releases/' + str(RELEASE_ID)); assets = {item['name']: item for item in final['assets']}
    assert assets[NAME]['id'] == new['id'] and assets[NAME]['digest'] == 'sha256:' + result['sha256']
    assert assets['SHA256SUMS.txt']['id'] == new_sum['id']
    for name, old in existing.items():
        preserved = OLD_NAME if name == NAME else SUM_OLD if name == 'SHA256SUMS.txt' else name
        assert assets[preserved]['id'] == old['id'] and assets[preserved]['digest'] == old['digest']
    result['assets'] = {name: {key: item[key] for key in ['id', 'digest', 'size']} for name, item in assets.items()}
    (output / 'publication.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='changed_files'}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sevenzip', default='7z'); parser.add_argument('--publish', action='store_true')
    args = parser.parse_args(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    if args.publish:
        assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_REF') == 'refs/heads/main'
        base = output / 'published-before-back-to-top.zip'
        with base.open('xb') as stream:
            subprocess.run(['gh', 'api', 'repos/' + REPO + '/releases/assets/' + str(BASE_ID), '-H', 'Accept: application/octet-stream'], stdout=stream, check=True, timeout=900)
    else:
        if args.base is None:
            parser.error('--base is required for a local build')
        base = args.base.resolve()
    target, sums, result = build(base, output, args.sevenzip)
    if args.publish:
        publish(output, target, sums, result)
    else:
        print(json.dumps({k:v for k,v in result.items() if k!='changed_files'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
