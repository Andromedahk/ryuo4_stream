import socket, struct, binascii
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
        ln,rid2,flags,err=struct.unpack('>IIBH',rx(11))
        data=rx(ln-11)
        if flags & 0x80: return err,data
def wstr(t):
    b=t.encode(); return struct.pack('>I',len(b))+b
cmd(1,8)
err,d=cmd(1,2,wstr('Landroid/app/ActivityThread;'))
print('err',err,'len',len(d),'hex',d.hex())
print('as list',list(d))
