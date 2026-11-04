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
BASE_ID = 695097125
SUM_ID = 695097124
BASE_SHA = 'd40de4b1404af73c3555d6e7028bed328d38e68299db108c2677ed55ceecfd86'
SUM_SHA = '802758a7777953b2a847aa1eb9df8379bdfbfc567d944cbc2db278a56bee072d'
PREFIX = 'MOSS-Image-Character-Catalog/'
NAME = 'MOSS-Image-Character-Catalog-v0.1.2.zip'
STAGED_NAME = NAME.replace('.zip', '-shuffle.zip')
OLD_NAME = NAME.replace('.zip', '-before-shuffle.zip')
SUM_STAGED = 'SHA256SUMS-shuffle.txt'
SUM_OLD = 'SHA256SUMS-before-shuffle.txt'


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


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f'Unexpected source anchor: {old[:100]}')
    return source.replace(old, new, 1)

def transform(source):
    original = "  function visible(){const query=currentQuery(),order=$('sort').value;if(!query.sorted||query.sortOrder!==order){query.sorted=query.matches.slice().sort((a,b)=>compareRecords(a,b,order));query.sortOrder=order;optimizerStats.sorts++;}return query.sorted;}"
    replacement = """  function visible(){
    const query=currentQuery(),order=$('sort').value;
    if(!query.sorted||query.sortOrder!==order){
      const records=query.matches.slice();
      if(order==='shuffle'){
        for(let index=records.length-1;index>0;index--){
          const other=Math.floor(Math.random()*(index+1));
          [records[index],records[other]]=[records[other],records[index]];
        }
      }else{
        records.sort((a,b)=>compareRecords(a,b,order));
      }
      query.sorted=records;
      query.sortOrder=order;
      optimizerStats.sorts++;
    }
    return query.sorted;
  }"""
    source = replace_once(source, original, replacement)
    source = replace_once(source, "sort:$('sort').value,language", "sort:$('sort').value==='shuffle'?sortBeforeShuffle:$('sort').value,language")
    source = replace_once(source, "  function localize(){localizeBackToTop();", "  function localize(){localizeBackToTop();localizeShuffle();")
    source = replace_once(source, "    const all=visible(),records=pageRecords(all),query=currentQuery();", "    const all=visible(),records=pageRecords(all),query=currentQuery();\n    const shuffle=$('shuffle-results');\n    if(shuffle)shuffle.disabled=all.length<2;")
    source = replace_once(source, "$('sort').addEventListener('change',()=>{page=1;storePreferences();render({facets:false});});", "$('sort').addEventListener('change',()=>{page=1;localizeShuffle();storePreferences();render({facets:false});});")
    setup = """  let sortBeforeShuffle='copyright';
  function localizeShuffle(){
    const control=$('shuffle-results');
    if(!control)return;
    control.textContent=language==='ja'?'🔀 シャッフル':'🔀 Shuffle';
    $('shuffle-sort-status').textContent=language==='ja'?'シャッフル中':'Shuffled';
  }
  function setupShuffle(){
    const sort=$('sort');
    const status=new Option('Shuffled','shuffle');
    status.id='shuffle-sort-status';
    status.hidden=true;
    status.disabled=true;
    sort.append(status);
    const control=document.createElement('button');
    control.id='shuffle-results';
    control.type='button';
    control.disabled=true;
    sort.closest('label').after(control);
    control.addEventListener('click',()=>{
      const query=currentQuery();
      if(query.matches.length<2)return;
      if(sort.value!=='shuffle')sortBeforeShuffle=sort.value;
      sort.value='shuffle';
      query.sorted=null;
      page=1;
      render({facets:false});
      storePreferences();
    });
  }

  setupShuffle();
"""
    return replace_once(source, "  setupBackToTop();\n", setup + "  setupBackToTop();\n")

def build(base, output, sevenzip):
    assert digest(base) == BASE_SHA
    output.mkdir(parents=True, exist_ok=True)
    target = output / STAGED_NAME
    assert not target.exists()
    script = 'app/review/review.js'
    with zipfile.ZipFile(base) as old:
        updated = transform(old.read(PREFIX + script).decode('utf-8'))
        updated = replace_once(
            updated,
            "    query.copyrightTotals=null;if(query.sortOrder==='copyright')query.sorted=null;",
            """    query.copyrightTotals=null;
    if(query.sortOrder==='copyright'||(query.sortOrder==='shuffle'&&isMatched)){
      query.sorted=null;
    }""",
        ).encode('utf-8')
        records = json.loads(old.read(PREFIX + 'app/outputs/user_catalog.json'))['items']
        assert len(records) == 34249
        assert PREFIX + 'SHA256SUMS.txt' not in old.namelist()
    assert hashlib.sha256(updated).hexdigest() == 'af241ae6fdebe5c9d6121b1fe0ab67c2aaaa13f27adbf593d659489a1a2767cf'
    replacements = {script: updated}
    for name in ('README.md', 'README.ja.md'):
        replacements[name] = (ROOT / name).read_bytes()
    stage = output / 'stage'
    for name, blob in replacements.items():
        path = stage / PREFIX / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    subprocess.run(['node', '--check', str(stage / PREFIX / script)], check=True)
    shutil.copy2(base, target)
    listing = output / 'update-files.txt'
    listing.write_text('\n'.join(PREFIX + name for name in replacements) + '\n', 'utf-8')
    subprocess.run([sevenzip, 'u', '-tzip', '-mm=Deflate', '-mx=5', '-scsUTF-8',
                    '-up1q1r2x2y2z2w2', str(target), '@' + str(listing)], cwd=stage, check=True)
    subprocess.run([sevenzip, 't', str(target)], check=True)
    unchanged = 0
    with zipfile.ZipFile(base) as old, zipfile.ZipFile(target) as new, base.open('rb') as a, target.open('rb') as b:
        assert len(old.infolist()) == len(new.infolist()) == len(set(new.namelist()))
        assert set(old.namelist()) == set(new.namelist())
        for entry in old.infolist():
            name = entry.filename.removeprefix(PREFIX)
            if name in replacements:
                assert new.read(entry.filename) == replacements[name]
            else:
                current = new.getinfo(entry.filename)
                assert compressed_digest(a, entry) == compressed_digest(b, current)
                unchanged += 1
        assert unchanged == 137069
    checksum = digest(target)
    sums = output / SUM_STAGED
    sums.write_bytes((checksum + '  ' + NAME + '\n').encode('ascii'))
    result = {'source_sha256': BASE_SHA, 'sha256': checksum, 'size': target.stat().st_size,
              'unchanged_compressed_entries': unchanged, 'images_verified': len(records),
              'changed_files': list(replacements)}
    (output / 'verification.json').write_text(json.dumps(result, indent=2), 'utf-8')
    return target, sums, result


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
    body += '**Shuffle / シャッフル（2026-11-04）**\n\nUse the button beside Sort by to shuffle filtered results. Both tabs preserve the order across pages.\n\nキャラクター・スタイルの検索・絞り込み結果をシャッフルできます。ページをめくっても順番は固定です。'
    body += f'\n\n34,249 images: 33,935 characters + 314 styles. All remaining image SHA256 values and {result["unchanged_compressed_entries"]:,} untouched compressed payloads verified. Previous ZIP/checksum retained as before-shuffle.\n\n```text\n{result["sha256"]}  {NAME}\n```\n'
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
        base = output / 'published-before-shuffle.zip'
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
