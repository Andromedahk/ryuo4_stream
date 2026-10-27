import socket, struct
s=socket.create_connection(('127.0.0.1',8700),timeout=10); s.settimeout(15)
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
        if flags & 0x80:
            return err,data
def rstr(d,o):
    n=struct.unpack('>I',d[o:o+4])[0]; return d[o+4:o+4+n].decode('utf-8','replace'), o+4+n
print('Version err',cmd(1,1)[0])
err,d=cmd(1,7); print('IDSizes err',err,'data',d.hex())
err,d=cmd(1,3); n=struct.unpack('>I',d[:4])[0]; print('VM.Classes count',n)
off=4; want={}
for i in range(min(n,4000)):
    tag=d[off]; tid=struct.unpack('>Q',d[off+1:off+9])[0]; off+=9
    sig,off=rstr(d,off); st=struct.unpack('>I',d[off:off+4])[0]; off+=4
    if sig in ('Landroid/app/ActivityThread;','Lcom/baiyi/homeui/hshomeui/MainActivity;'):
        want[sig]=(tag,tid,st)
print('wanted',want)
for sig,(tag,tid,st) in want.items():
    err,d=cmd(9,1,struct.pack('>Q',tid)); print(sig,'Signature err',err,'len',len(d),'hex',d.hex()[:80])
    err,d=cmd(9,4,struct.pack('>Q',tid)); print(' Field err',err,'len',len(d))
    err,d=cmd(9,5,struct.pack('>Q',tid)); print(' Methods err',err,'len',len(d), 'count', struct.unpack('>I',d[:4])[0] if len(d)>=4 else None)
