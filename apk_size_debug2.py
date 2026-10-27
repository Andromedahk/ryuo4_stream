import os,shutil,zipfile,subprocess
BASE=r"D:\ROG longwang4"; BT=os.path.join(BASE,r"tools\android-sdk\build-tools\33.0.2"); JDK=os.path.join(BASE,r"tools\jdk-21.0.12.1+1")
SRC=os.path.join(BASE,r"apk\build\base.apk"); WORK=os.path.join(BASE,r"firmware-build\dbg2")
def run(pad, extra):
    if os.path.isdir(WORK): shutil.rmtree(WORK)
    os.makedirs(WORK)
    p=os.path.join(WORK,'b.apk'); shutil.copyfile(SRC,p)
    with zipfile.ZipFile(p,'a',zipfile.ZIP_STORED) as z:
        zi=zipfile.ZipInfo('assets/pad.bin',date_time=(2020,1,1,0,0,0)); zi.compress_type=zipfile.ZIP_STORED
        z.writestr(zi,b'\x00'*pad)
        if extra:
            zi2=zipfile.ZipInfo('assets/e.bin',date_time=(2020,1,1,0,0,0)); zi2.compress_type=zipfile.ZIP_STORED
            z.writestr(zi2,b'\x00'*extra)
    a=os.path.join(WORK,'a.apk'); subprocess.run([os.path.join(BT,'zipalign.exe'),'-f','4',p,a],check=True,capture_output=True)
    out=os.path.join(WORK,'s.apk'); env=dict(os.environ); env['JAVA_HOME']=JDK; env['PATH']=os.path.join(JDK,'bin')+';'+env.get('PATH','')
    subprocess.run([os.path.join(BT,'apksigner.bat'),'sign','--ks',os.path.join(BASE,r'apk\debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','ryuo','--v1-signing-enabled','false','--v2-signing-enabled','true','--v3-signing-enabled','true','--out',out,a],check=True,capture_output=True,env=env)
    return os.path.getsize(out)
for extra in (0,100,200,300,400,500,600):
    s=run(4000,extra); print('extra',extra,'size',s,'mod4096',s%4096)
