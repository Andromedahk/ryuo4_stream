import socket, struct
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
        hdr=rx(11)
        ln,rid2,flags,err=struct.unpack('>IIBH',hdr)
        data=rx(ln-11)
        print('  req %d/%d -> hdr=%s len=%d id=%d flags=0x%02x err=%d data(len=%d)=%s' % (cs,cm,hdr.hex(),ln,rid2,flags,err,len(data),data[:40].hex()))
        if flags & 0x80: return err,data
cmd(1,1)
err,d=cmd(1,3); n=struct.unpack('>I',d[:4])[0]
off=4; tid=None
for i in range(n):
    tag=d[off]; t=struct.unpack('>Q',d[off+1:off+9])[0]; off+=9
    ln2=struct.unpack('>I',d[off:off+4])[0]; sig=d[off+4:off+4+ln2].decode('utf-8','replace'); off+=4+ln2
    off+=4
    if sig=='Landroid/app/ActivityThread;': tid=t; break
print('ActivityThread tid',tid)
for cs,cm in [(9,1),(9,9),(9,3),(3,1),(9,10)]:
    try: cmd(cs,cm,struct.pack('>Q',tid))
    except Exception as e: print('   EXC',e)
