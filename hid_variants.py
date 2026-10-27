import sys, json, time
sys.path.insert(0,r"D:\ROG longwang4")
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
variants=[
 {"waterBlockScreen":{"enable":True},"pad":"x"*400},
 {"waterBlockScreen":{"enable":True,"displayInSleep":True,"brightness":85},"pad":"x"*350},
 {"waterBlockScreen":{"enable":True,"id":{"id":"Customization"}},"pad":"x"*330},
 {"waterBlockScreen":{"id":{"id":"Customization","screenMode":"Full Screen","playMode":"Single"}},"pad":"x"*300},
 {"waterBlockScreen":{"id":{"media":["a.mp4"]}},"pad":"x"*330},
 {"waterBlockScreen":{"id":{"settings":{"titleColor":"#E5252B"}}},"pad":"x"*330},
 {"waterBlockScreen":{"id":{"sysinfoDisplay":["","","","","",""]}},"pad":"x"*300},
 {"waterBlockScreen":{"id":{"timeZone":"Asia/Shanghai"}},"pad":"x"*330},
]
for i,v in enumerate(variants):
    b=json.dumps(v,separators=(",",":")).encode()
    print("VARIANT",i,"len",len(b),"Zcount",b.count(b"Z"))
    send_post(dev,"config",[],b)
    time.sleep(0.5)
