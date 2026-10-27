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
def clssig(sig):
    err,d=cmd(1,2,struct.pack('>I',len(sig))+sig.encode())
    if err: return None
    tag=d[4]; return struct.unpack('>Q',d[5:13])[0]
def methods(tid):
    err,d=cmd(2,5,struct.pack('>Q',tid)); n=struct.unpack('>I',d[:4])[0]; o=4; out=[]
    for i in range(n):
        m=struct.unpack('>Q',d[o:o+8])[0]; o+=8
        l=struct.unpack('>I',d[o:o+4])[0]; nm=d[o+4:o+4+l].decode(); o+=4+l
        l=struct.unpack('>I',d[o:o+4])[0]; sg=d[o+4:o+4+l].decode(); o+=4+l
        mod=struct.unpack('>I',d[o:o+4])[0]; o+=4
        out.append((m,nm,sg,mod))
    return out
cmd(1,8)
err,d=cmd(1,4); ids=[struct.unpack('>Q',d[4+i*8:12+i*8])[0] for i in range(struct.unpack('>I',d[:4])[0])]
for t in ids:
    err,d=cmd(11,1,struct.pack('>Q',t))
    if err==0 and d[4:4+struct.unpack('>I',d[:4])[0]].decode()=='main': main=t
print('main',hex(main))
for sig,mn in [('Ljava/lang/Thread;','activeCount'),('Landroid/app/ActivityThread;','currentActivityThread')]:
    tid=clssig(sig); print(sig,'tid',hex(tid))
    err,d=cmd(3,1,struct.pack('>Q',tid)); print(' superclass err',err,'data',d.hex() if err==0 else '')
    ms=methods(tid); mid=[m for m in ms if m[1]==mn][0][0]
    print(' method',mn,hex(mid), [x for x in ms if x[1]==mn][0][2])
    for t in [main]+ids[:4]:
        payload=struct.pack('>QQQII',tid,t,mid,0,0)
        err,d=cmd(3,3,payload)
        print('  invoke thread',hex(t),'err',err,'data',d.hex() if err==0 else '')
        if err==0: break
cmd(1,9)
