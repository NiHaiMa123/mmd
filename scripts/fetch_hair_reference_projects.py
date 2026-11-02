"""Download independently published free reference files; inventory only, execute nothing."""
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(r'E:\project\mmd\work\hair_reference_projects_20261102')
ROOT.mkdir(exist_ok=True)
SOURCES = [
    ('Sextet_Actor3_2021', 'https://b31a5bd0-cf89-4ecb-b668-fa5139389d9e.filesusr.com/archives/dedff5_ea2f334f16a44149916bea3ddeb2d40a.zip?dn=Actor3.0.zip', 'https://www.bilibili.com/video/BV1yy4y1a72y/'),
    ('Sextet_Actor3_2022_CC0', 'https://b31a5bd0-cf89-4ecb-b668-fa5139389d9e.filesusr.com/archives/dedff5_85aeb3fc635245f485177a1068780636.zip?dn=Actor3.0.zip', 'https://www.bilibili.com/video/BV1vd4y1N7hm/'),
    ('Wiggle2_2023_bug_reproduction', 'https://blenderartists.org/uploads/short-url/qtfkzE6pI2KRJCbehRpM4JehMp4.blend', 'https://blenderartists.org/t/wiggle-2/1454788/105'),
]
rows, blocked_hosts = [], set()
for name, url, source in SOURCES:
    host = urllib.parse.urlparse(url).hostname
    if host in blocked_hosts:
        rows.append(dict(name=name, url=url, status='SKIPPED_HOST_DENIAL'))
        continue
    suffix = '.zip' if '.zip' in url else '.blend'
    path = ROOT / (name + suffix)
    row = dict(name=name, url=url, author_source=source, path=str(path))
    try:
        if not path.exists():
            request = urllib.request.Request(url, headers={'User-Agent':'MMD-reference-research/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                row['http_status'] = response.status
                row['content_type'] = response.headers.get('Content-Type')
                body = response.read(64*1024*1024+1)
                assert len(body) <= 64*1024*1024, 'Reference exceeds this diagnostic download limit'
                assert 'text/html' not in (row['content_type'] or '').lower(), 'HTML page instead of asset'
            path.write_bytes(body)
        row.update(status='DOWNLOADED_NOT_EXECUTED', size=path.stat().st_size,
                   sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                row['members'] = [dict(name=x.filename, bytes=x.file_size) for x in archive.infolist()]
                blend_files = []
                for i, info in enumerate(x for x in archive.infolist() if x.filename.lower().endswith('.blend')):
                    assert info.file_size <= 128*1024*1024
                    # Fixed output name; never trust archive paths for extraction.
                    target = ROOT / f'{name}_{i+1}.blend'
                    target.write_bytes(archive.read(info))
                    blend_files.append(str(target))
                row['blend_files'] = blend_files
        else:
            assert path.stat().st_size > 12
            row['blend_files'] = [str(path)]
    except urllib.error.HTTPError as exc:
        row.update(status='HTTP_FAILED', error_code=exc.code)
        if exc.code in [401,403,412,429]:
            blocked_hosts.add(host)
    except Exception as exc:
        row.update(status='FETCH_OR_VALIDATION_FAILED', error=repr(exc))
    rows.append(row)
    (ROOT / 'downloads.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in row.items() if k not in ['members']},ensure_ascii=False),flush=True)
