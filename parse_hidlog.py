import re
lines=open(r'D:\ROG longwang4\device-notes\hidlog_raw.txt',encoding='utf-8',errors='replace').read().splitlines()
for i,l in enumerate(lines):
    l=l.strip()
    m=re.search(r'([0-9A-Fa-f]{20,})\s*$', l)
    if m:
        h=m.group(1)
        print(i, 'len',len(h)//2, 'head',h[:24],'tail',h[-24:])
