import sys, json, time
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_post, DEFAULT_JSON
dev=pick_target(find_devices())
j=json.loads(json.dumps(DEFAULT_JSON))
j['waterBlockScreen']['id']['media']=['2026-10-07_11-59-09-827.mp4']
body=json.dumps(j,separators=(',',':')).encode()
for i in range(3):
    send_post(dev,'config',[],body)
    time.sleep(0.7)
