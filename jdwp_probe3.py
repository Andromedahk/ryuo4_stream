import socket, struct, binascii
s=socket.create_connection(('127.0.0.1',8700),timeout=10); s.settimeout(10)
s.sendall(b'JDWP-Handshake'); s.recv(14)
rid=0
def rx(n):
    b=b''
    while len(b)<n:
        c=s.recv(n-len(b));
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
def rstr(d,o):
    n=struct.unpack('>I',d[o:o+4])[0]; return d[o+4:o+4+n].decode(), o+4+n
cmd(1,8)
err,d=cmd(1,2,wstr('Landroid/app/ActivityThread;'))
cnt=struct.unpack('>I',d[:4])[0]; off=4
entries=[]
for i in range(cnt):
    tag=d[off]; tid=struct.unpack('>Q',d[off+1:off+9])[0]; st=struct.unpack('>I',d[off+9:off+13])[0]; off+=13
    entries.append((tag,tid,st))
print('entries',entries)
tid=entries[0][1]
for cs,cm in [(9,1),(9,4),(9,5),(9,2)]:
    if (cs,cm)==(9,2): continue
    err,d=cmd(cs,cm,struct.pack('>Q',tid))
    print('cmd',cs,cm,'err',err,'len',len(d),'hex',binascii.hexlify(d[:60]))
    if (cs,cm)==(9,1) and err==0:
        print('sig:', rstr(d,0)[0])
    if (cs,cm)==(9,5) and err==0:
        n=struct.unpack('>I',d[:4])[0]; print('methods',n)
        o=4
        for i in range(min(n,8)):
            mid=struct.unpack('>Q',d[o:o+8])[0]; o+=8
            nm,o=rstr(d,o); sg,o=rstr(d,o); mod=struct.unpack('>I',d[o:o+4])[0]; o+=4
            print(' ',hex(mid),nm,sg)
    if (cs,cm)==(9,4) and err==0:
        n=struct.unpack('>I',d[:4])[0]; print('fields',n)
        o=4
        for i in range(min(n,10)):
            fid=struct.unpack('>Q',d[o:o+8])[0]; o+=8
            nm,o=rstr(d,o); sg,o=rstr(d,o); mod=struct.unpack('>I',d[o:o+4])[0]; o+=4
            print(' ',hex(fid),nm,sg)
