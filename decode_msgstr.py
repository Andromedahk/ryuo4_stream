import re
path=r'D:\ROG longwang4\device-notes\hid_msgstr.txt'
data=open(path,'rb').read().decode('utf-8-sig','replace')
for line in data.splitlines():
    line=line.strip()
    m=re.search(r'msgStr--([0-9A-Fa-f]+)', line)
    if not m: continue
    b=bytes.fromhex(m.group(1))
    txt=''.join(chr(c) if 32<=c<127 else '.' for c in b[:130])
    print('len',len(b),'head',b[:6].hex(),'|',txt)
