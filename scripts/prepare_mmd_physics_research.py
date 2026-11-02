import json,re,tomllib,zipfile,zlib
from pathlib import Path
ROOT=Path(r'E:\project\mmd');OUT=ROOT/'work/headswap_xl_codex/mmd_physics_sources_20261031';OUT.mkdir(parents=True,exist_ok=True)
BASE=Path(r'E:\project\bilibili');config=tomllib.loads((BASE/'config.toml').read_text('utf8'))
for key in ['media_cache','output_dir','temp_dir']:config['paths'][key]=str(OUT/('bilibili_'+key))
for section,keys in [('paths',['bdl_cli','ffmpeg','ffprobe']),('bilibili',['cookie_file']),('asr',['python','model_path','aligner_path'])]:
 for key in keys:
  value=config.get(section,{}).get(key)
  if value and not Path(value).is_absolute():config[section][key]=str(BASE/value)
def literal(v):return str(v).lower() if isinstance(v,bool) else json.dumps(v,ensure_ascii=True)
text='\n\n'.join('['+section+']\n'+'\n'.join(key+' = '+literal(value) for key,value in values.items()) for section,values in config.items())
(OUT/'bilibili.config.toml').write_text(text,'utf8')
archive=next(Path(r'E:\data\模之屋\渲染\【夏安】BREAK ME DOWN!! - プレコ feat. 知声\工程文件').glob('*.zip'));target=ROOT/'work/headswap_xl_codex/lookdev_reference_20261028/author_project/BREAK ME DOWN!! 20260902.blend'
with zipfile.ZipFile(archive) as z:
 entries=[dict(name=i.filename,bytes=i.file_size,crc32=i.CRC) for i in z.infolist()];blend=next(i for i in z.infolist() if i.filename.endswith('.blend'));crc=0
 with target.open('rb') as stream:
  for block in iter(lambda:stream.read(16*1024*1024),b''):crc=zlib.crc32(block,crc)
 report=dict(archive=str(archive),inspected_blend=str(target),matches_original_archive=target.stat().st_size==blend.file_size and crc==blend.CRC,entries=entries)
 (OUT/'archive_inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
 for i in z.infolist():
  if i.filename.lower().endswith(('.txt','.md')):
   data=z.read(i)
   for encoding in ['utf-8-sig','gb18030','shift_jis']:
    try:content=data.decode(encoding);break
    except UnicodeDecodeError:continue
   else:content=data.decode('utf8','replace')
   (OUT/'author_archive_text.txt').write_text(content,'utf8')
print(json.dumps(dict(output=str(OUT),original_blend_crc_match=report['matches_original_archive'],archive_files=len(entries)),ensure_ascii=True))
