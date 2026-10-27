import socket, struct
s=socket.create_connection(('127.0.0.1',8700),timeout=10); s.settimeout(30)
s.sendall(b'JDWP-Handshake'); s.recv(14)
rid=0
def rx(n):
    b=b''
    while len(b)<n:
        c=s.recv(n-len(b))
        if not c: raise Exception('closed')
        b+=c
    return b
def cmd(cs,cm,payload=b''):
    global rid; rid+=1
    s.sendall(struct.pack('>II',len(payload)+11,rid)+bytes([0,cs,cm])+payload)
    while True:
        ln,rid2,flags,err=struct.unpack('>IIBH',rx(11))
        data=rx(ln-11)
        if flags & 0x80: return err,data
def rstr(d,o):
    n=struct.unpack('>I',d[o:o+4])[0]; return d[o+4:o+4+n].decode('utf-8','replace'), o+4+n
err,d=cmd(1,3); n=struct.unpack('>I',d[:4])[0]
print('classes',n)
off=4; found={}; first=None
for i in range(n):
    tag=d[off]; tid=struct.unpack('>Q',d[off+1:off+9])[0]; off+=9
    sig,off=rstr(d,off); st=struct.unpack('>I',d[off:off+4])[0]; off+=4
    if first is None: first=(tag,tid,sig)
    if sig in ('Landroid/app/ActivityThread;','Lcom/baiyi/homeui/hshomeui/MainActivity;','Landroid/widget/VideoView;'):
        found[sig]=(tag,tid,st)
print('found',found)
print('first',first)
for label,(tag,tid,sig) in [('first',first)]+list(found.items()):
    err,d=cmd(9,1,struct.pack('>Q',tid)); print(label,tag,hex(tid),'sig cmd err',err,'hex',d.hex()[:100])
for sig,(tag,tid,st) in found.items():
    err,d=cmd(9,5,struct.pack('>Q',tid)); print(sig,'Methods err',err,'len',len(d),'count',struct.unpack('>I',d[:4])[0] if len(d)>=4 else None)
    err,d=cmd(9,4,struct.pack('>Q',tid)); print(sig,'Fields err',err,'len',len(d),'count',struct.unpack('>I',d[:4])[0] if len(d)>=4 else None)
