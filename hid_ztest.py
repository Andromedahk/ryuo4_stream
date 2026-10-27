import sys, json, time
sys.path.insert(0,r"D:\ROG longwang4")
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
tests=[
 ("neutral_Z", {"pad":"Z"+"x"*400}),
 ("neutral_noZ", {"pad":"z"+"x"*400}),
 ("timezone_lower", {"waterBlockScreen":{"id":{"timezone":"Asia/Shanghai"}},"pad":"x"*300}),
 ("timeZone_upper", {"waterBlockScreen":{"id":{"timeZone":"Asia/Shanghai"}},"pad":"x"*300}),
]
for name,v in tests:
    b=json.dumps(v,separators=(",",":")).encode()
    print("TEST",name,"len",len(b),"Z",b.count(b"Z"))
    send_post(dev,"config",[],b)
    time.sleep(0.6)
