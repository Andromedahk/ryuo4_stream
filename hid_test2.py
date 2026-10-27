import sys
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_post, build_frame, send_frame
dev=pick_target(find_devices())
# 1) big conn with 300-byte body
body=b'A'*300
send_post(dev,'conn',[],body)
# 2) config with the exact original media list (no URL)
import json
j={"temperature":"Celsius","waterBlockScreen":{"enable":True,"displayInSleep":True,"brightness":85,
 "id":{"id":"Customization","screenMode":"Full Screen","playMode":"Single",
 "media":["2026-10-07_11-59-09-827.mp4","RYUO_IV_HW_Info_05.mp4"],
 "settings":{"titleColor":"#E5252B","contentColor":"#FFFFFF","filter":{"value":None,"opacity":100},"badges":[]},
 "sysinfoDisplay":["","","","","",""],"timeZone":"Asia/Shanghai"}},
 "spec":{"cpu":"AMD Ryzen 7 9700X","gpu":"NVIDIA GeForce RTX 5090"}}
b=json.dumps(j,separators=(',',':')).encode()
send_post(dev,'config',[],b)
