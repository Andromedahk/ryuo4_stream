import sys, struct, binascii
sys.path.insert(0,r'D:\ROG longwang4')
import jdb_inject as J
j=J.JDWP('127.0.0.1',8700)
try: j.suspend()
except Exception as e: print('suspend',e)
for sig in ['Landroid/app/ActivityThread;','Ljava/lang/String;','Lcom/baiyi/homeui/hshomeui/MainActivity;']:
    cls=j.classes_by_sig(sig)
    print('==',sig,cls)
    if not cls: continue
    tid=cls[0][0]
    # 9/1 Signature
    try:
        d=j.cmd(9,1,struct.pack('>Q',tid))
        s,_=j.rstr(d,0); print('  sig:',s)
    except Exception as e: print('  sig ERR',e)
    # 9/5 methods raw
    try:
        d=j.cmd(9,5,struct.pack('>Q',tid))
        print('  methods raw len',len(d),binascii.hexlify(d[:64]))
        n=struct.unpack('>I',d[:4])[0]; print('  count',n)
    except Exception as e: print('  methods ERR',e)
    # 9/4 fields
    try:
        d=j.cmd(9,4,struct.pack('>Q',tid)); print('  fields raw len',len(d), binascii.hexlify(d[:32]))
    except Exception as e: print('  fields ERR',e)
j.resume()
