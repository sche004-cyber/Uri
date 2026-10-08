import json,socket
from pathlib import Path
out={}
for name,path,op in [('authorized_write',Path('inside.txt'),'write'),('outside_read',Path('../protected.txt'),'read'),('outside_write',Path('../outside.txt'),'write')]:
 try:
  path.write_text('harmless marker') if op=='write' else path.read_text()
  out[name]='ALLOWED'
 except Exception as error: out[name]=type(error).__name__
print(json.dumps(out))
