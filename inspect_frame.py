import sys, json, struct
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import DEFAULT_JSON, build_frame, next_seq
j=json.loads(json.dumps(DEFAULT_JSON))
j['waterBlockScreen']['id']['media']=['2026-10-07_11-59-09-827.mp4']
body=json.dumps(j,separators=(',',':')).encode()
h=[('SeqNumber','123'),('Date','123'),('ContentType','json'),('ContentLength',str(len(body)))]
f=build_frame('config','1',h,body)
print('len',len(f),'head',f[:3].hex(),'tail',f[-2:].hex())
print('body',body.decode())
for b in (0x5A,0x0D,0x0A,0x00):
    pos=[i for i,c in enumerate(f) if c==b]
    print(hex(b),'count',len(pos),'positions(first20)',pos[:20])
