"""Fetch public author Blender sources, including one regular Git LFS media object."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(r'E:\project\mmd\work\hair_reference_projects_20261102')
assets = [
    dict(name='TressFX_Blender_Hair_Source', url='https://raw.githubusercontent.com/ismailivanov/TressFX-Godot/main/addons/tressfx/demo/blender_hair/source/blender_hair.blend', size=2300712),
    dict(name='Scthe_Unity_Hair_Source', url='https://media.githubusercontent.com/media/Scthe/unity-hair/master/unity-hair.blend',
         size=27850433, sha256='2a32f792a27beb8a85cb0be52bbcdc0970b6fcafc1fe31f7f808610166f32e57'),
]
rows = []
for asset in assets:
    path = ROOT / (asset['name']+'.blend')
    row = dict(asset, path=str(path), execution=False)
    try:
        if not path.exists():
            request = urllib.request.Request(asset['url'], headers={'User-Agent':'MMD-reference-research/1.0'})
            with urllib.request.urlopen(request, timeout=45) as response:
                assert 'text/html' not in response.headers.get('Content-Type','')
                data = response.read(64*1024*1024+1)
            assert len(data) <= 64*1024*1024
            path.write_bytes(data)
        assert path.stat().st_size == asset['size'], (path.stat().st_size, asset['size'])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if 'sha256' in asset:
            assert digest == asset['sha256'], 'Git LFS object hash mismatch'
        row.update(status='DOWNLOADED_SIZE_AND_HASH_CHECKED', sha256=digest)
    except Exception as exc:
        row.update(status='FAILED', error=repr(exc))
    rows.append(row)
    (ROOT / 'source_blend_downloads.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(row,ensure_ascii=False),flush=True)
