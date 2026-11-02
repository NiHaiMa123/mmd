"""Read VMD record counts before treating a camera file as character motion."""
import json
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
for path in Path('E:/data').rglob('*.vmd'):
    data=path.read_bytes();offset=50
    result={'file':str(path),'bytes':len(data),'model':data[30:50].split(b'\0')[0].decode('cp932',errors='replace')}
    for name,size in [('bone',111),('morph',23),('camera',61),('light',28),('shadow',9)]:
        if offset+4>len(data):break
        count=struct.unpack_from('<I',data,offset)[0];offset+=4
        assert offset+count*size<=len(data),(path,name,count)
        frames=[struct.unpack_from('<I',data,offset+i*size+(15 if name in ('bone','morph') else 0))[0] for i in range(count)]
        result[name]={'records':count,'last_frame':max(frames,default=0)}
        offset+=count*size
    print(json.dumps(result,ensure_ascii=False,indent=2))
