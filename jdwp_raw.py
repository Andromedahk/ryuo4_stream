import socket, struct, binascii
s=socket.create_connection(('127.0.0.1',8700),timeout=10); s.settimeout(10)
s.sendall(b'JDWP-Handshake')
def rx(n):
    b=b''
    while len(b)<n:
        c=s.recv(n-len(b))
        if not c: raise Exception('closed')
        b+=c
    return b
print('hs', rx(14))
rid=0
def cmd(cs,cm,payload=b''):
    global rid
    rid+=1
    pkt=struct.pack('>II',len(payload)+11,rid)+bytes([0])+bytes([cs,cm])+payload
    s.sendall(pkt)
    while True:
        hdr=rx(11)
        ln,rid2,flags,err=struct.unpack('>IIBH',hdr)
        data=rx(ln-11)
        print('reply: len=%d id=%d flags=0x%02x err=%d data=%s' % (ln,rid2,flags,err,binascii.hexlify(data[:80])))
        if flags & 0x80:
            return err,data
# 1/1 Version
cmd(1,1)
# suspend
cmd(1,8)
# all threads
cmd(1,4)
# classes by sig
cmd(1,2, J:=struct.pack('>I',len('Landroid/app/ActivityThread;'))+b'Landroid/app/ActivityThread;')
cmd(9,1,struct.pack('>Q',1))
cmd(9,5,struct.pack('>Q',1))
