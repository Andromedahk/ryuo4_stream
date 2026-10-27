import re
log = r"C:\Users\ZZZX\AppData\Roaming\rog_infohub\logs\2026-10-27.log"
lines = open(log, encoding='utf-8', errors='replace').read().splitlines()
print("lines:", len(lines))
cmds = []
i = 0
while i < len(lines):
    if 'adb exec cmdArgs:' in lines[i]:
        s = lines[i].split('adb exec cmdArgs:',1)[1].strip()
        j = i+1
        while j < len(lines) and not re.match(r'^\d\d:\d\d:\d\d', lines[j]) and j < i+10:
            s += ' ' + lines[j].strip()
            j += 1
        cmds.append(re.sub(r'\s+',' ', s))
    i += 1
print("total adb exec commands:", len(cmds))
seen=set()
for c in cmds:
    if c not in seen:
        seen.add(c); print("CMD:", c[:500])
print("\n=== keyword lines ===")
kw = re.compile(r'MediaStation|pushMedia|waterBlock|ffmpeg|videoStream|CatchVideo|mediaFrameGet|4244|reverse|forward|shell|am start|sdcard', re.I)
count=0
for ln in lines:
    if kw.search(ln):
        print(ln[:600]); count+=1
        if count>150: break
