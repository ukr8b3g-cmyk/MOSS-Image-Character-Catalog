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
BASE_ID = 694686283
SUM_ID = 694686285
BASE_SHA = '0578b09a68f73fdebcd2f47601af4994748728666cdb9a191143fd0a17507831'
SUM_SHA = 'e19a79445b75edac041858827cea7c47a9fdcc81684a4f10850a3f5a8cea27c4'
PREFIX = 'MOSS-Image-Character-Catalog/'
NAME = 'MOSS-Image-Character-Catalog-v0.1.2.zip'
STAGED_NAME = NAME.replace('.zip', '-prompt-revision.zip')
OLD_NAME = NAME.replace('.zip', '-before-prompt-revision.zip')
SUM_STAGED = 'SHA256SUMS-prompt-revision.txt'
SUM_OLD = 'SHA256SUMS-before-prompt-revision.txt'


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
    import copy,collections,csv,io
    from prompt_revision_rules import repair_caption,flags,ui_changes,REV
    assert digest(base)==BASE_SHA
    output.mkdir(parents=True,exist_ok=True); target=output/STAGED_NAME
    assert not target.exists()
    replacements={};counts=collections.Counter();csv_rows=[];review_rows=[]
    fixed_time='2026-10-31T08:47:34+00:00'
    with zipfile.ZipFile(base) as z:
        original=json.loads(z.read(PREFIX+'app/outputs/user_catalog.json'))
        merged=copy.deepcopy(original)
        edits=json.loads(z.read(PREFIX+'app/outputs/user_catalog_edits.json'))
        original_edits=copy.deepcopy(edits)
        assert len(merged['items'])==34249
        for old,r in zip(original['items'],merged['items']):
            overlay=edits['edits'].get('user/'+r['id'],{})
            fields=overlay.get('fields',{})
            effective=fields.get('copy_prompt',r['copy_prompt'])
            new,why=repair_caption(effective,r['kind']=='character')
            future,_=repair_caption(r['generation_prompt'],r['kind']=='character')
            fs=flags(r,effective)
            counts['copy_changed']+=new!=effective
            counts['generation_changed']+=future!=r['generation_prompt']
            counts['flagged_records']+=bool(fs)
            counts[r['kind']]+=1
            r.update(copy_prompt=new,reuse_generation_prompt=future,prompt_revision=REV,prompt_review_flags=fs,updated_at=fixed_time)
            if 'copy_pr\x7fmpt_file' in r['files']:
                r['files']['copy_prompt_file']=r['files'].pop('copy_pr\x7fmpt_file');counts['file_keys_repaired']+=1
            if 'copy_prompt' in fields:fields['copy_prompt']=new;overlay['updated_at']=fixed_time
            side='app/outputs/'+r['files']['copy_prompt_file']
            side_bytes=(new+'\n').encode('utf-8')
            if z.read(PREFIX+side).decode('utf-8').strip()!=new:replacements[side]=side_bytes
            assert 'tail tip if present' not in new.lower() and 'tail tip if present' not in future.lower()
            assert r['generation_prompt']==old['generation_prompt']
            assert {k:v for k,v in old.items() if k not in {'copy_prompt','files','updated_at'}}=={k:v for k,v in r.items() if k not in {'copy_prompt','files','updated_at','reuse_generation_prompt','prompt_revision','prompt_review_flags'}}
            csv_rows.append({'id':r['id'],'kind':r['kind'],'name':fields.get('name',r['name']),'copy_prompt':new,'reuse_generation_prompt':future,'review_flags':';'.join(fs)})
            if fs:review_rows.append({'id':r['id'],'name':fields.get('name',r['name']),'review_flags':';'.join(fs)})
        assert dict(counts)=={'copy_changed':5641,'generation_changed':33785,'flagged_records':15946,'character':33935,'file_keys_repaired':3,'style':314},dict(counts)
        for key,old in original_edits['edits'].items():
            new=edits['edits'][key]
            assert {k:v for k,v in old.items() if k not in {'fields','updated_at'}}=={k:v for k,v in new.items() if k not in {'fields','updated_at'}}
            assert {k:v for k,v in old['fields'].items() if k!='copy_prompt'}=={k:v for k,v in new['fields'].items() if k!='copy_prompt'}
        html,js=ui_changes(z.read(PREFIX+'app/review/index.html').decode('utf-8'),z.read(PREFIX+'app/review/review.js').decode('utf-8'))
        replacements['app/review/index.html']=html.encode('utf-8');replacements['app/review/review.js']=js.encode('utf-8')
    replacements['app/outputs/user_catalog.json']=(json.dumps(merged,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    replacements['app/outputs/user_catalog_edits.json']=(json.dumps(edits,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    for name,rows,fields in [('revised-prompts.csv',csv_rows,['id','kind','name','copy_prompt','reuse_generation_prompt','review_flags']),('review-needed.csv',review_rows,['id','name','review_flags'])]:
        f=io.StringIO(newline='');writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        replacements['docs/prompt-repair-20261031/'+name]=f.getvalue().encode('utf-8-sig')
    for name in ['README.md','README.ja.md','docs/updates/prompt-revision.md','docs/prompt-repair-20261031/README.md','docs/prompt-repair-20261031/README.ja.md']:
        replacements[name]=(ROOT/name).read_bytes()
    # No stale self-checksum is bundled inside its own archive.
    with zipfile.ZipFile(base) as z:assert PREFIX+'SHA256SUMS.txt' not in z.namelist()
    stage=output/'stage'
    for n,b in replacements.items():
        p=stage/PREFIX/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    subprocess.run(['node','--check',str(stage/PREFIX/'app/review/review.js')],check=True)
    shutil.copy2(base,target)
    listing=output/'update-files.txt';listing.write_text('\n'.join(PREFIX+n for n in replacements)+'\n','utf-8')
    subprocess.run([sevenzip,'u','-tzip','-mm=Deflate','-mx=5','-scsUTF-8','-up1q1r2x2y2z2w2',str(target),'@'+str(listing)],cwd=stage,check=True)
    subprocess.run([sevenzip,'t',str(target)],check=True)
    with zipfile.ZipFile(base) as old,zipfile.ZipFile(target) as new,base.open('rb') as af,target.open('rb') as bf:
        a={i.filename:i for i in old.infolist()};b={i.filename:i for i in new.infolist()}
        assert len(b)==len(new.infolist());assert set(b)==set(a)|{PREFIX+n for n in replacements}
        unchanged=0
        for n,i in b.items():
            rel=n.removeprefix(PREFIX)
            if rel in replacements:assert new.read(n)==replacements[rel]
            else:
                p=a[n];assert (i.CRC,i.file_size,i.compress_size,i.compress_type)==(p.CRC,p.file_size,p.compress_size,p.compress_type)
                assert compressed_digest(af,p)==compressed_digest(bf,i);unchanged+=1
        for j,r in enumerate(merged['items'],1):
            assert hashlib.sha256(new.read(PREFIX+'app/outputs/'+r['files']['image'])).hexdigest()==r['image_sha256']
            if j%10000==0:print('Verified unchanged image hashes:',j,flush=True)
    checksum=digest(target);sums=output/SUM_STAGED;sums.write_text(checksum+'  '+NAME+'\n','ascii')
    result={'source_sha256':BASE_SHA,'sha256':checksum,'size':target.stat().st_size,'entries':len(b),'unchanged_compressed_entries':unchanged,'images_verified':34249,'characters':33935,'styles':314,'counts':dict(counts),'changed_files':list(replacements),'historical_prompts_preserved':True,'current_copy_and_future_tail_tip_matches':0}
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
    body += (ROOT/'docs/updates/prompt-revision.md').read_text('utf-8')
    body += f'\n\n34,249 images: 33,935 characters + 314 styles. All remaining image SHA256 values and {result["unchanged_compressed_entries"]:,} untouched compressed payloads verified. Previous ZIP/checksum retained as before-prompt-revision.\n\n```text\n{result["sha256"]}  {NAME}\n```\n'
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
        base = output / 'published-before-prompt-revision.zip'
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

