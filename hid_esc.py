import sys, json, time
sys.path.insert(0,r"D:\ROG longwang4")
from hid_send import find_devices, pick_target, send_post, DEFAULT_JSON
dev=pick_target(find_devices())
j=json.loads(json.dumps(DEFAULT_JSON))
j['waterBlockScreen']['id']['media']=['2026-10-07_11-59-09-827.mp4']
b=json.dumps(j,separators=(',',':')).encode()
orig_z=b.count(b'Z')
b=b.replace(b'Z',b'\\u005A')
print("bodylen",len(b),"origZ",orig_z,"nowZ",b.count(b'Z'))
send_post(dev,"config",[],b)
