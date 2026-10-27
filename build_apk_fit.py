#!/usr/bin/env python3
"""Build an APK whose total byte size exactly equals TARGET (16,798 bytes) so it
can replace SharedStorageBackup.apk in the system image without changing the
ext4 inode size or adding trailing bytes.

Method: start from the prebuilt unsigned base APK (manifest + resources.arsc),
insert classes.dex, append a ZIP_STORED padding entry, zipalign, then sign with
APK Signature Scheme v2+v3 only (no v1 -> saves ~2 KB so the exact size fits).
Iterate the padding so the signed size is exactly TARGET.
"""
import os, sys, shutil, subprocess, zipfile, struct

BASE = r"D:\ROG longwang4"
BT = os.path.join(BASE, r"tools\android-sdk\build-tools\33.0.2")
JDK = os.path.join(BASE, r"tools\jdk-21.0.12.1+1")
KEYSTORE = os.path.join(BASE, r"apk\debug.keystore")
SRC_BASE = os.path.join(BASE, r"apk\build\base.apk")
SRC_DEX = os.path.join(BASE, r"apk\build\dex\classes.dex")
OUT = os.path.join(BASE, r"firmware-build\ryuo-stream-fw.apk")
TARGET = 16798
WORK = os.path.join(BASE, r"firmware-build\apkwork")

def build(pad):
    os.makedirs(WORK, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)
    base = os.path.join(WORK, 'base.apk')
    shutil.copyfile(SRC_BASE, base)
    # base.apk already contains AndroidManifest.xml, resources.arsc and classes.dex
    with zipfile.ZipFile(base, 'a', zipfile.ZIP_STORED) as z:
        zi = zipfile.ZipInfo('assets/pad.bin', date_time=(2020, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b'\x00' * pad)
    aligned = os.path.join(WORK, 'aligned.apk')
    subprocess.run([os.path.join(BT, 'zipalign.exe'), '-f', '4', base, aligned], check=True,
                   capture_output=True)
    ext = os.path.join(BT, 'apksigner.bat')
    env = dict(os.environ)
    env['JAVA_HOME'] = JDK
    env['PATH'] = os.path.join(JDK, 'bin') + ';' + env.get('PATH', '')
    subprocess.run([ext, 'sign', '--ks', KEYSTORE, '--ks-pass', 'pass:android',
                    '--key-pass', 'pass:android', '--ks-key-alias', 'ryuo',
                    '--v1-signing-enabled', 'false', '--v2-signing-enabled', 'true',
                    '--v3-signing-enabled', 'true', '--out', OUT, aligned],
                   check=True, capture_output=True, env=env)
    return os.path.getsize(OUT)

def main():
    pad = 0
    size = build(pad)
    print('pad=0 -> %d' % size)
    for it in range(8):
        delta = TARGET - size
        if delta == 0:
            break
        pad += delta
        if pad < 0:
            pad = 0
        size = build(pad)
        print('pad=%d -> %d (delta %d)' % (pad, size, TARGET - size))
        if size == TARGET:
            break
    if size != TARGET:
        raise SystemExit('could not hit exact size, last %d' % size)
    print('OK exact size', size)

if __name__ == '__main__':
    main()

