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
        print('  %d/%d hdr=%s len=%d id=%d flags=0x%02x err=%d data=%s' % (cs,cm,hdr.hex(),ln,rid2,flags,err,data[:40].hex()))
        if flags&0x80: return err,data
cmd(1,8)
err,d=cmd(1,4)
ids=[struct.unpack('>Q',d[4+i*8:12+i*8])[0] for i in range(struct.unpack('>I',d[:4])[0])]
print('thread ids',[hex(i) for i in ids])
cmd(10,1,struct.pack('>Q',ids[0]))
cmd(10,2,struct.pack('>Q',ids[0]))
cmd(10,4,struct.pack('>Q',ids[0]))
cmd(10,6,struct.pack('>QI',ids[0],0)+struct.pack('>I',1))
