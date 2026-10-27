import sys, struct
sys.path.insert(0,r'D:\ROG longwang4')
import jdb_inject as J
j=J.JDWP('127.0.0.1',8700)
j.suspend()
ts=j.all_threads()
print('threads count',len(ts),[hex(t) for t in ts[:15]])
for t in ts[:20]:
    try:
        d=j.cmd(10,1,struct.pack('>Q',t)); nm,_=j.rstr(d,0)
    except Exception as e:
        nm='ERR '+str(e)
    print(hex(t),nm)
j.resume()
