import sys, json, time
sys.path.insert(0,r"D:\ROG longwang4")
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
expr=sys.argv[1]
# expr like {"waterBlockScreen":{"enable":true},"pad":"x"*400}
try:
    body=eval(expr).encode() if False else None
except Exception:
    body=None
# build JSON via python eval of dict literal expressions with * allowed
val=eval(expr)
body=json.dumps(val,separators=(",",":")).encode()
print("bodylen",len(body))
send_post(dev,"config",[],body)
