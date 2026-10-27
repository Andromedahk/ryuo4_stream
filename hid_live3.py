import sys, json, time
sys.path.insert(0,r"D:\ROG longwang4")
from hid_send import find_devices, pick_target, send_post, DEFAULT_JSON
dev=pick_target(find_devices())
j=json.loads(json.dumps(DEFAULT_JSON))
j['waterBlockScreen']['id']['media']=['live3.mp4']
b=json.dumps(j,separators=(',',':')).encode().replace(b'Z',b'\\u005A')
send_post(dev,"config",[],b)
