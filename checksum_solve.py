frames=[
 ('conn','5A0038504F535420636F6E6E20310D0A5365714E756D6265723D333739320D0A446174653D313739333037373339353234340D0A0D0A055A',0x05),
 ('ack','5A004131203230300D0A41636B4E756D6265723D333739340D0A436F6E74656E744C656E6774683D300D0A436F6E74656E74547970653D6A736F6E0D0A0D0A415A',0x41),
]
cands=[]
for a in range(0,5):
    for b in range(len(bytes.fromhex(frames[0][1]))-3, len(bytes.fromhex(frames[0][1]))+1):
        pass
# generic: function over slice [a:b] of each frame, b may be len (include tail) or len-1 (exclude last 5A)
funcs={
 'sum': lambda x: sum(x)&0xff,
 'xor': lambda x: __import__('functools').reduce(lambda p,c:p^c,x,0),
 'sum_notail': lambda x: sum(x)&0xff,
}
for name,fn in funcs.items():
    for a in range(0,5):
        for bmode in ['len','len-1','len-2','len-3']:
            ok=True; details=[]
            for label,h,chk in frames:
                bs=bytes.fromhex(h); L=len(bs)
                b={'len':L,'len-1':L-1,'len-2':L-2,'len-3':L-3}[bmode]
                v=fn(bs[a:b])
                details.append((label,hex(v),hex(chk)))
                if v!=chk: ok=False
            if ok: print('MATCH',name,'a',a,'b',bmode,details)
print('done simple; try crc8 variants')
# try common crc8
def crc8(data, poly=0x07, init=0x00, refin=False, refout=False, xorout=0x00):
    crc=init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc=((crc<<1)^poly)&0xff if crc&0x80 else (crc<<1)&0xff
    return crc^xorout
for poly in (0x07,0x31,0x9b,0x39,0xd5):
    for a in (0,1,2,3):
        for bmode in ('len-2','len-1','len'):
            ok=True
            for label,h,chk in frames:
                bs=bytes.fromhex(h); L=len(bs)
                b={'len-2':L-2,'len-1':L-1,'len':L}[bmode]
                if crc8(bs[a:b],poly)!=chk: ok=False
            if ok: print('CRC8 MATCH poly',hex(poly),'a',a,bmode)
