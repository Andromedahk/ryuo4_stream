import sys, json, time
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
tests=[
 json.dumps({"waterBlockScreen":{"enable":True},"pad":"x"*400},separators=(',',':')),
 json.dumps({"temperature":"Celsius","waterBlockScreen":{"enable":True,"brightness":85},"pad":"x"*400},separators=(',',':')),
 json.dumps({"pad":"x"*400,"waterBlockScreen":{"enable":True}},separators=(',',':')),
]
for t in tests:
    b=t.encode(); print('len',len(b)); send_post(dev,'config',[],b); time.sleep(0.6)
