"""Fetch the pinned public community PR into a new local directory, verifying its source."""
import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

COMMIT='00a01ff31f8d4cea3c07efd5f030e3f15b93398a'
BASE_COMMIT='792db09a22cd5c7dc5b5c1b4eb0ea12c4af3e6b1'
SOURCE_SHA256='1334a8b452745fc7201cf6c05d6982bfe0a33b2c67335420025b260cb16c2b57'
BLOB_SHA1='e65b6da85983481146dd9e633f3cb658bcf7d111'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    vendor=out/'vendor'
    assert not vendor.exists(),'Existing vendor preserved; select a new output directory'
    url=f'https://codeload.github.com/Noisysundae/blender-jiggle-physics-ns/zip/{COMMIT}'
    request=urllib.request.Request(url,headers={'User-Agent':'MMD-pinned-community-reproduction'})
    with urllib.request.urlopen(request,timeout=45) as response:data=response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        roots={n.split('/')[0] for n in archive.namelist()}
        assert len(roots)==1
        prefix=next(iter(roots))
        source=archive.read(prefix+'/__init__.py')
        assert hashlib.sha256(source).hexdigest()==SOURCE_SHA256,'Unexpected community source'
        assert hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()==BLOB_SHA1
        for name in archive.namelist():
            assert (vendor/name).resolve().is_relative_to(vendor.resolve()),name
        vendor.mkdir()
        archive.extractall(vendor)
    package=out/f'jiggle_pr47_{COMMIT[:12]}.zip';package.write_bytes(data)
    record=dict(repository='Noisysundae/blender-jiggle-physics-ns',commit=COMMIT,base_commit=BASE_COMMIT,
                pr_url='https://github.com/naelstrof/blender-jiggle-physics/pull/47',pr_unmerged_at_2026_11_02=True,
                github_blob_sha=BLOB_SHA1,github_blob_sha_verified=True,source_sha256=SOURCE_SHA256,
                source_dir=str(vendor/prefix),archive=str(package),archive_sha256=hashlib.sha256(data).hexdigest(),
                url=url,local_solver_edits=False)
    (out/'plugin_provenance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
