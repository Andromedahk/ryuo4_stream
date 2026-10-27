import sys, json
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
for cmd in ['all','STATE','preset','cmd','config']:
    body=json.dumps({"test":cmd}).encode()
    print('sending',cmd)
    send_post(dev,cmd,[],body)
    import time; time.sleep(0.4)
