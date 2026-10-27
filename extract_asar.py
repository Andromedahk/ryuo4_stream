import json, os, struct, sys
src = r"C:\Program Files\ASUS Info Hub - ROG RYUO IV\resources\app.asar"
out = r"D:\ROG longwang4\host-re\asar"
with open(src,'rb') as f:
    data = f.read()
hdr_len = struct.unpack('<I', data[12:16])[0]
header = json.loads(data[16:16+hdr_len].decode('utf-8'))
base = (16 + hdr_len + 3) & ~3
print("jsonlen", hdr_len, "base", base, "firstbytes", data[base:base+8])
os.makedirs(out, exist_ok=True)
count=0; total=0
def walk(node, path):
    global count,total
    for name, meta in node.get('files',{}).items():
        p = path + '/' + name if path else name
        if 'files' in meta:
            walk(meta, p)
        else:
            off = int(meta.get('offset',0)); size = int(meta.get('size',0))
            if 'link' in meta: continue
            fp = os.path.join(out, *p.split('/'))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp,'wb') as g: g.write(data[base+off:base+off+size])
            count+=1; total+=size
walk(header,'')
print("files:",count,"bytes:",total)
