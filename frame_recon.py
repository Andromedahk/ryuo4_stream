import json, struct
# Reconstruct the exact config ASCII captured in the device log
body=('{"temperature":"Celsius","waterBlockScreen":{"enable":true,"displayInSleep":true,"brightness":85,'
 '"id":{"id":"Customization","screenMode":"Full Screen","playMode":"Single","media":["2026-10-07_11-59-09-827.mp4","RYUO_IV_HW_Info_05.mp4","RYUO_IV_HW_Info_01.mp4","RYUO_IV_HW_Info_02.mp4","RYUO_IV_HW_Info_03.mp4","RYUO_IV_HW_Info_04.mp4"],'
 '"settings":{"titleColor":"#E5252B","contentColor":"#FFFFFF","filter":{"value":null,"opacity":100},"badges":[]},'
 '"sysinfoDisplay":["","","","","",""],"timeZone":"Asia/Shanghai"}},"spec":{"cpu":"AMD Ryzen 7 9700X","gpu":"NVIDIA GeForce RTX 5090"}}')
print('body len',len(body.encode()))
ascii_=('POST config 1\r\nSeqNumber=3793\r\nDate=1793077396413\r\nContentType=json\r\nContentLength=%d\r\n\r\n'%len(body.encode()))+body
print('ascii len',len(ascii_))
total=3+len(ascii_)+2
print('total',total,hex(total))
head=bytes([0x5A])+struct.pack('>H',total)
chk=(sum(head[1:])+sum(ascii_.encode()))&0xFF
print('checksum',hex(chk),'expected 0x37')
frame=head+ascii_.encode()+bytes([chk,0x5A])
print('frame len',len(frame),'head',frame[:4].hex(),'tail',frame[-3:].hex())
