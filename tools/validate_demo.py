"""Validate the public sample boundary with Python's standard library only."""
import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'demo'
FIELDS = {'name','name_jp','name_cn','copyright','kind','copy_prompt','copy_tags',
          'subject_type','facets','rendered_at','added_at','id','key','run_id',
          'demo_image','image_sha256','source_count','generated','hidden','deleted','favorite','similarity'}


def validate():
    data = json.loads((SITE / 'catalog.json').read_text(encoding='utf-8'))
    rows = data['entries']
    assert collections.Counter(r['kind'] for r in rows) == {'character':96,'style':24}
    assert len({r['key'] for r in rows}) == 120
    assert data['visibility_mode'] == 'readonly-demo'
    assert data['runs'] == data['style_candidates'] == []
    referenced = set()
    for row in rows:
        assert set(row) <= FIELDS, 'Unexpected public metadata field'
        assert row['generated'] is True
        if row['kind'] == 'character':
            assert isinstance(row['source_count'], int) and row['source_count'] >= 0
        assert not any(row[k] for k in ('hidden','deleted','favorite','similarity'))
        assert re.fullmatch(r'images/[0-9]{3}\.webp',row['demo_image'])
        path = SITE / row['demo_image']
        assert not path.is_symlink()
        blob = path.read_bytes()
        assert hashlib.sha256(blob).hexdigest() == row['image_sha256'], str(path)
        assert blob[:4] == b'RIFF' and blob[8:12] == b'WEBP'
        assert int.from_bytes(blob[4:8],'little') + 8 == len(blob)
        offset = 12
        image_found = False
        while offset < len(blob):
            tag = blob[offset:offset+4]
            assert tag not in (b'EXIF',b'XMP '), 'Private image metadata remains'
            image_found |= tag in (b'VP8 ',b'VP8L',b'ANMF')
            size = int.from_bytes(blob[offset+4:offset+8],'little')
            offset += 8 + size + size % 2
        assert offset == len(blob) and image_found
        referenced.add(row['demo_image'])
    expected = referenced | {'index.html','review.js','review.css','catalog.json','.nojekyll'}
    actual = {p.relative_to(SITE).as_posix() for p in SITE.rglob('*') if p.is_file()}
    assert actual == expected, 'Unexpected or missing deployed files'
    payload = (SITE/'catalog.json').read_text(encoding='utf-8')
    assert not re.search(r'[A-Za-z]:[\\/]|127\.0\.0\.|operation_id|request_digest|source_filename|"token"',payload)
    html = (SITE/'index.html').read_text(encoding='utf-8')
    js = (SITE/'review.js').read_text(encoding='utf-8')
    css = (SITE/'review.css').read_text(encoding='utf-8')
    assert 'data-catalog-mode="demo"' in html
    assert 'connect-src \'self\'' in html
    assert 'new URL(\'catalog.json\',location.href)' in js
    assert "if(demoMode)throw new Error(t('demoReadOnly'))" in js
    assert 'html[data-catalog-mode="demo"] .actions' in css
    category_index = json.loads((ROOT/'docs/style-categories.json').read_text(encoding='utf-8'))
    assert len(category_index['categories']) == 8 and len(category_index['assignments']) == 314
    import csv
    with (ROOT/'docs/style-categories.csv').open(encoding='utf-8-sig',newline='') as stream:
        category_rows = list(csv.DictReader(stream))
    assert len(category_rows) == 314
    assert len({r['catalog_key'] for r in category_rows}) == 314
    assert {r['catalog_key']:r['category_id'] for r in category_rows} == category_index['assignments']
    assert set(category_index['assignments'].values()) == {c['id'] for c in category_index['categories']}
    category_names={r['name']:r['category_id'] for r in category_rows}
    verification=json.loads((ROOT/'docs/validation/style93-generation.json').read_text(encoding='utf-8'))
    assert verification['status']=='completed' and verification['verified_images']==93
    assert len(verification['items'])==93 and len({i['key'] for i in verification['items']})==93
    for item in verification['items']:
        assert item['key'] in category_index['assignments']
        assert re.fullmatch(r'[0-9a-f]{64}',item['sha256'])
    demo_category_index={**category_index,'assignments':{r['key']:category_names[r['name']] for r in rows if r['kind']=='style'}}
    for attrs, candidates in re.findall(r'<script type="application/json"([^>]*)>(.*?)</script>',html,re.S):
        if 'id="style-category-index"' in attrs:
            assert json.loads(candidates) == demo_category_index
        else:
            assert json.loads(candidates) == [], 'Full source candidate list leaked'
    total = sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file())
    assert total < 20_000_000, 'Unexpected demo growth; review publication scope'
    for name in ['README.md','README.ja.md']:
        text = (ROOT/name).read_text(encoding='utf-8')
        for required in ['33,937','221','34,158','314','34,251','docs/updates/style93-generation.md','245','559','33,935','34,249','2.07 GB','1.93 GiB',
                         '/releases/download/v0.1.2/MOSS-Image-Character-Catalog-v0.1.2.zip',
                         'MOSS_Image_Character_Sample.json','MOSS_Image_Style_Sample.json',
                         '8961184','1.0','25','2.5']:
            assert required in text, (name,required)
        assert '0.7' not in text and not re.search(r'[CD]:[\\/]',text)
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in target or target.startswith('#'): continue
            assert (ROOT/target.split('#')[0]).is_file(), (name,target)
    print(json.dumps({'passed':True,'characters':96,'styles':24,'files':len(actual),'bytes':total}))


if __name__ == '__main__':
    validate()

