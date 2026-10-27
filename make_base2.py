import os, subprocess
FF=r"C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\ffmpeg.exe"
OUT=r"D:\ROG longwang4\stream_test"
SLOT=770048  # 4096*188, 2 seconds @ 3.08 Mbps
DUR=2
N=10
NULL=bytes([0x47,0x1F,0xFF,0x10])+b'\xFF'*184
def make(path,layer,lavfi,pts):
    args=[FF,'-hide_banner','-y','-loglevel','error','-f','lavfi','-i',lavfi,'-t',str(DUR),
      '-c:v','libx264','-preset','ultrafast','-tune','zerolatency','-pix_fmt','yuv420p',
      '-b:v','2500k','-maxrate','2500k','-bufsize','1250k','-g','30','-muxrate','3080192',
      '-output_ts_offset',str(pts),'-f','mpegts',path]
    subprocess.run(args,check=True)
    return open(path,'rb').read()
def pad(d):
    if len(d)>SLOT: raise SystemExit('chunk too big %d'%len(d))
    return d+NULL*((SLOT-len(d))//188)
parts=[]
for k in range(N):
    raw=make(os.path.join(OUT,'b%02d.ts'%k),None,'testsrc2=size=1920x960:rate=30',k*DUR)
    parts.append(pad(raw)); print('slot',k,len(raw))
base=b''.join(parts); open(os.path.join(OUT,'base2.ts'),'wb').write(base)
print('base size',len(base),'expect',SLOT*N)
for k in (5,6):
    raw=make(os.path.join(OUT,'r%02d.ts'%k),None,'color=red:size=1920x960:rate=30',k*DUR)
    open(os.path.join(OUT,'red2_%02d.bin'%k),'wb').write(pad(raw)); print('red',k,len(raw))
