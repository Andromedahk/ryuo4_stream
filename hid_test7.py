import sys, json, time
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_post
dev=pick_target(find_devices())
variants=[
 ('url', {"pad":"x"*500,"u":"http://127.0.0.1:18080/live.ts"}),
 ('hash', {"pad":"x"*450,"c":"#E5252B"}),
 ('settings', {"pad":"x"*420,"settings":{"titleColor":"#E5252B","contentColor":"#FFFFFF","filter":{"value":None,"opacity":100},"badges":[]}}),
 ('media_local', {"pad":"x"*400,"media":["2026-10-07_11-59-09-827.mp4"]}),
]
for name,v in variants:
    b=json.dumps(v,separators=(',',':')).encode()
    print(name,'bodylen',len(b)); send_post(dev,'config',[],b); time.sleep(0.6)
