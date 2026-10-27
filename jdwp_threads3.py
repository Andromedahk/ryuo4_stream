import socket,struct,binascii
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
        print('  %d/%d len=%d err=%d data=%s' % (cs,cm,ln,err,data.hex()[:160]))
        if flags&0x80: return err,data
cmd(1,1)
cmd(1,8)
err,d=cmd(1,4)
print('count',struct.unpack('>I',d[:4])[0], 'datalen',len(d))
print('first ids',[struct.unpack('>Q',d[4+i*8:12+i*8])[0] for i in range(5)])
