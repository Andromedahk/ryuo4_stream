import sys, struct
sys.path.insert(0,r'D:\ROG longwang4')
import jdb_inject as J
j=J.JDWP('127.0.0.1',8700)
j.suspend()
ts=j.all_threads()
at=j.classes_by_sig('Landroid/app/ActivityThread;')[0][0]
mid=[m for m in j.methods(at) if m[1]=='currentActivityThread'][0][0]
for opt in (0,2):
    for t in ts:
        payload=struct.pack('>QQQII',at,t,mid,0,opt)
        try:
            d=j.cmd(3,3,payload)
            tag=chr(d[0]); off=1
            if tag in 'L[s': v=struct.unpack('>Q',d[off:off+8])[0]; off+=8
            elif tag=='V': v=None
            elif tag=='I': v=struct.unpack('>i',d[off:off+4])[0]; off+=4
            else: v=None
            exc=struct.unpack('>Q',d[off:off+8])[0] if len(d)>=off+8 else 0
            print('opt',opt,'thread',hex(t),'tag',tag,'obj',v,'exc',exc)
            if v: raise SystemExit
        except Exception as e:
            print('opt',opt,'thread',hex(t),'ERR',e)
j.resume()
