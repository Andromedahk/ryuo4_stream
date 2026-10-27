import sys, struct
sys.path.insert(0,r'D:\ROG longwang4')
import jdb_inject as J
j=J.JDWP('127.0.0.1',8700)
j.suspend()
for sig in ['Lcom/baiyi/homeui/hshomeui/MainActivity;','Landroid/app/ActivityThread;']:
    cls=j.classes_by_sig(sig)
    print(sig,cls)
    tid=cls[0][0]
    for cs,cm in [(2,1),(2,9),(2,3)]:
        try:
            d=j.cmd(cs,cm,struct.pack('>Q',tid))
            print('  ',cs,cm,'len',len(d),'data',d[:60].hex())
            if cs==2 and cm==1:
                s,_=j.rstr(d,0); print('   sig=',s)
        except Exception as e: print('  ',cs,cm,'ERR',e)
j.resume()
