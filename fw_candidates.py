import json,os
p=r"D:\ROG longwang4\firmware\unpacked\idx-system.json"
j=json.load(open(p,encoding='utf-8'))
print(type(j), list(j.keys())[:10] if isinstance(j,dict) else len(j))
files=j['files'] if isinstance(j,dict) else j
print('count',len(files))
print('first',files[0])
cands=[f for f in files if f['path'].lower().endswith('.apk') and 16000 <= f['size'] <= 400000]
for c in sorted(cands,key=lambda x:x['size']):
    print(c['size'], c['ino'], c['path'])
