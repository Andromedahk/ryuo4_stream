import sys, json, time
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
body=json.dumps({"pad":"x"*455}).encode()
print('bodylen',len(body))
for i in range(3):
    send_post(dev,'config',[],body); time.sleep(0.5)
