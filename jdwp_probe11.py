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
err,d=cmd(1,4); ids=[struct.unpack('>Q',d[4+i*8:12+i*8])[0] for i in range(struct.unpack('>I',d[:4])[0])]
# find main
main=None
for t in ids:
    err,d=cmd(11,1,struct.pack('>Q',t))
    if err==0:
        n=struct.unpack('>I',d[:4])[0]; nm=d[4:4+n].decode()
        print(hex(t),nm)
        if nm=='main': main=t
print('main',hex(main))
print('suspend thread err',cmd(11,2,struct.pack('>Q',main))[0])
# class id + method
err,d=cmd(1,2,struct.pack('>I',len('Landroid/app/ActivityThread;'))+b'Landroid/app/ActivityThread;')
tid=struct.unpack('>Q',d[5:13])[0]; print('AT tid',hex(tid))
err,d=cmd(2,5,struct.pack('>Q',tid)); n=struct.unpack('>I',d[:4])[0]; o=4; mid=None
for i in range(n):
    m=struct.unpack('>Q',d[o:o+8])[0]; o+=8
    ln2=struct.unpack('>I',d[o:o+4])[0]; nm=d[o+4:o+4+ln2].decode(); o+=4+ln2
    ln3=struct.unpack('>I',d[o:o+4])[0]; sg=d[o+4:o+4+ln3].decode(); o+=4+ln3
    o+=4
    if nm=='currentActivityThread': mid=m; print('found',nm,sg,hex(m))
for opt in (0,2):
    payload=struct.pack('>QQQII',tid,main,mid,0,opt)
    err,d=cmd(3,3,payload); print('invoke opt',opt,'err',err,'data',d.hex())
    if err==0:
        print('tag',chr(d[0]),'obj',struct.unpack('>Q',d[1:9])[0])
        break
cmd(1,9)
