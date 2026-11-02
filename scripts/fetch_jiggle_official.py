import urllib.request, json, hashlib, zipfile, io
from pathlib import Path
p=Path(r'E:\project\mmd\work\headswap_xl_codex\jiggle_physics_20261031');p.mkdir(exist_ok=True)
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'MMD-local-plugin-reproduction'}),timeout=45) as r:return r.read()
meta=json.loads(get('https://api.github.com/repos/naelstrof/blender-jiggle-physics/commits/main'))
sha=meta['sha'];url=f'https://codeload.github.com/naelstrof/blender-jiggle-physics/zip/{sha}'
blob=get(url); archive=p/f'jiggle_physics_{sha[:12]}.zip';archive.write_bytes(blob)
target=p/'vendor';target.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(blob)) as z:
    for name in z.namelist():
        dest=(target/name).resolve()
        assert dest.is_relative_to(target.resolve()),name
    z.extractall(target)
record=dict(repository='https://github.com/naelstrof/blender-jiggle-physics',commit=sha,url=url,sha256=hashlib.sha256(blob).hexdigest(),archive=str(archive),source_dir=str(target/f'blender-jiggle-physics-{sha}'))
(p/'plugin_provenance.json').write_text(json.dumps(record,indent=2),'utf8');print(json.dumps(record),flush=True)
