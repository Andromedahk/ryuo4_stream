import sys
sys.path.insert(0,r'D:\ROG longwang4')
import jdb_inject as J
j=J.JDWP('127.0.0.1',8700)
print('attached')
try: j.suspend()
except Exception as e: print('suspend:',e)
at=j.classes_by_sig('Landroid/app/ActivityThread;')
print('classes:',at)
if at:
    ms=j.methods(at[0][0])
    print('method count',len(ms))
    for mid,n,s,m in ms:
        if 'current' in n.lower() or 'Activity' in n:
            print(n,s)
    # also static fields containing activities
    fs=j.fields(at[0][0])
    print('fields count',len(fs))
    for f,n,s,m in fs:
        if 'ctiv' in n: print('FIELD',n,s)
j.resume()
