import sys, struct, json, time
sys.path.insert(0,r'D:\ROG longwang4')
from hid_send import find_devices, pick_target, send_frame
dev=pick_target(find_devices())
body=('{"temperature":"Celsius","waterBlockScreen":{"enable":true,"displayInSleep":true,"brightness":85,'
 '"id":{"id":"Customization","screenMode":"Full Screen","playMode":"Single","media":["2026-10-07_11-59-09-827.mp4","RYUO_IV_HW_Info_05.mp4","RYUO_IV_HW_Info_01.mp4","RYUO_IV_HW_Info_02.mp4","RYUO_IV_HW_Info_03.mp4","RYUO_IV_HW_Info_04.mp4"],'
 '"settings":{"titleColor":"#E5252B","contentColor":"#FFFFFF","filter":{"value":null,"opacity":100},"badges":[]},'
 '"sysinfoDisplay":["","","","","",""],"timeZone":"Asia/Shanghai"}},"spec":{"cpu":"AMD Ryzen 7 9700X","gpu":"NVIDIA GeForce RTX 5090"}}').encode()
ascii_=('POST config 1\r\nSeqNumber=3793\r\nDate=1793077396413\r\nContentType=json\r\nContentLength=%d\r\n\r\n'%len(body)).encode()+body
total=5+len(ascii_)
head=bytes([0x5A])+struct.pack('>H',total)
chk=(sum(head[1:])+sum(ascii_))&0xFF
frame=head+ascii_+bytes([chk,0x5A])
print('total',total,'len',len(frame),'chk',hex(chk),'expected 0x37')
ok,w,e=send_frame(dev,frame); print('write',ok,w,e)
