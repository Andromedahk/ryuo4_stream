import sys, json
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import DEFAULT_JSON, build_frame
j=json.loads(json.dumps(DEFAULT_JSON))
j['waterBlockScreen']['id']['media']=['2026-10-07_11-59-09-827.mp4']
body=json.dumps(j,separators=(',',':')).encode()
h=[('SeqNumber','123'),('Date','123'),('ContentType','json'),('ContentLength',str(len(body)))]
f=build_frame('config','1',h,body)
for i,c in enumerate(f):
    if c==0x5A: print('0x5A at',i,repr(f[max(0,i-25):i+10]))
print('ascii prefix:',f[3:120].decode())
