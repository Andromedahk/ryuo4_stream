import socket,struct
s=socket.create_connection(('127.0.0.1',8700),timeout=10); s.settimeout(10)
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
        hdr=rx(11); ln,rid2,flags,err=struct.unpack('>IIBH',hdr); data=rx(ln-11)
        if flags&0x80: return err,data
cmd(1,8)
# capabilities
for c in [(1,12),(1,17)]:
    err,d=cmd(*c); print('caps',c,'err',err,'data',d.hex())
err,d=cmd(1,5); print('TopLevelThreadGroups err',err,'data',d.hex())
gid=struct.unpack('>Q',d[4:12])[0] if len(d)>=12 else 0
print('group id',hex(gid))
err,d=cmd(1,4); ids=[struct.unpack('>Q',d[4+i*8:12+i*8])[0] for i in range(struct.unpack('>I',d[:4])[0])]
tid=ids[0]
for cs,cm,arg in [(10,1,tid),(11,1,tid),(10,1,gid),(11,1,gid),(10,4,tid),(11,4,gid)]:
    try:
        err,d=cmd(cs,cm,struct.pack('>Q',arg))
        print('cmd',cs,cm,'arg',hex(arg),'err',err,'data',d[:40].hex())
    except Exception as e: print('cmd',cs,cm,'EXC',e)
