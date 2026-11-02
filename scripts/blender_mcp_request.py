"""Client for the user's enabled local Blender MCP add-on transport."""
import argparse,json,socket
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--command',default='ping');p.add_argument('--code-file');p.add_argument('--response');p.add_argument('--timeout',type=float,default=45);a=p.parse_args()
request=dict(type='execute_code',params=dict(code=Path(a.code_file).read_text('utf-8-sig'))) if a.code_file else dict(type=a.command,params={})
with socket.create_connection(('127.0.0.1',9876),timeout=a.timeout) as conn:
    conn.settimeout(a.timeout);conn.sendall(json.dumps(request,ensure_ascii=False).encode('utf8'));buffer=b''
    while True:
        block=conn.recv(65536)
        if not block:raise RuntimeError('MCP disconnected before a complete response; inspect job status before retry')
        buffer+=block
        if len(buffer)>32*1024*1024:raise RuntimeError('Unexpected large response')
        try:response=json.loads(buffer.decode('utf8'));break
        except (json.JSONDecodeError,UnicodeDecodeError):continue
if a.response:Path(a.response).write_text(json.dumps(response,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(response,ensure_ascii=False,indent=2),flush=True)
assert response.get('status')=='success',response
