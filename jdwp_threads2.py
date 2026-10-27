import sys, struct, binascii
sys.path.insert(0,r'D:\ROG longwang4')
import jdb_inject as J
j=J.JDWP('127.0.0.1',8700)
# raw helpers
def raw(cs,cm,payload=b''):
    j.rid+=1
    pkt=struct.pack('>II',len(payload)+11,j.rid)+bytes([0,cs,cm])+payload
    j.s.sendall(pkt)
    while True:
        hdr=j._recv_exact(11)
        ln,rid2,flags,err=struct.unpack('>IIBH',hdr)
        data=j._recv_exact(ln-11)
        print('  %d/%d hdr=%s len=%d err=%d data=%s' % (cs,cm,hdr.hex(),ln,err,data[:40].hex()))
        if flags & 0x80: return err,data
j.suspend()
ts=j.all_threads()
print('threads',[hex(t) for t in ts])
for t in ts[:5]:
    raw(10,4,struct.pack('>Q',t))
# find ActivityThread class
at=j.classes_by_sig('Landroid/app/ActivityThread;')[0][0]
print('at id',hex(at))
ms=j.methods(at)
cur=[m for m in ms if m[1]=='currentActivityThread']
print('cur method',cur)
mid=cur[0][0]
for t in ts:
    try:
        tag,obj,exc=j.invoke(at,t,mid,[],class_invoke=True)
        print('thread',hex(t),'OK obj',obj,'exc',exc)
        if obj: break
    except Exception as e:
        print('thread',hex(t),'ERR',e)
j.resume()
