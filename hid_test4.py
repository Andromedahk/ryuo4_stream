import sys, json, time
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
tests=[('neutral', 'x'*n) for n in (10,100,200,300,400,500)]
tests.append(('water', None))
for name,pad in tests:
    if pad is None:
        body=json.dumps({"waterBlockScreen":{"enable":True}}).encode()
    else:
        body=json.dumps({"pad":pad}).encode()
    print(name, 'body', len(body))
    send_post(dev,'config',[],body)
    time.sleep(0.5)
