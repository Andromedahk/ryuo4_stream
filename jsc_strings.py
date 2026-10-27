import re, sys, os
def strings(path, minlen=4):
    data = open(path,'rb').read()
    out=[]
    # ascii
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % minlen, data):
        out.append(m.group().decode('ascii'))
    # utf16le
    for m in re.finditer(rb'(?:[\x20-\x7e]\x00){%d,}' % minlen, data):
        out.append(m.group().decode('utf-16le','replace'))
    return out
p = r"D:\ROG longwang4\host-re\asar\out\main\index.jsc"
ss = strings(p)
open(r"D:\ROG longwang4\host-re\jsc_strings.txt",'w',encoding='utf-8').write("\n".join(ss))
print("total strings:", len(ss))
kw = ['adb','ffmpeg','push','sdcard','h264','rtsp','udp','tcp','socket','fps','bitrate','resolution','2400','1080','screenrecord','surface','frame','rgb','raw','encode','decode','media','video','stream','display','lcd','panel','asus','ryuo','firmware','update','shell','exec','forward','reverse','scrcpy','minicap']
for k in kw:
    hits=[s for s in ss if k.lower() in s.lower()]
    print("### KW",k,len(hits))
    for s in hits[:12]:
        s=s.replace('\n',' ')
        print("   ", s[:300])
