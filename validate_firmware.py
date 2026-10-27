#!/usr/bin/env python3
"""Full offline validation of the modified firmware package."""
import os, sys, zipfile, hashlib, struct, subprocess, json

BASE = r"D:\ROG longwang4"
B = os.path.join(BASE, "firmware-build")
MOD = os.path.join(B, "ROG_RYUO_IV_Streaming_Firmware_MOD.zip")
ORIG = os.path.join(BASE, r"firmware\ROG_RYUO_IV_Series_Firmware_File.zip")
IMG = os.path.join(B, "system.img")
TMP_BR = os.path.join(B, "validate_system.new.dat.br")
TMP_IMG = os.path.join(B, "validate_system.img")
NODE = r"C:\Users\ZZZX\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
APK = os.path.join(BASE, r"apk\ryuo-stream-v2.apk")

def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()

def main():
    print('== 1. zip structure ==')
    zm = zipfile.ZipFile(MOD); zo = zipfile.ZipFile(ORIG)
    nm = zm.namelist(); no = zo.namelist()
    print('entries mod/orig:', len(nm), len(no), 'same order:', nm == no)
    print('testzip:', zm.testzip())
    for nm2, want in (('META-INF/com/android/metadata', 69), ('META-INF/com/android/metadata.pb', 489)):
        zi = zm.getinfo(nm2)
        print(nm2, 'data_offset', zi.header_offset + 30 + len(nm2) + len(zi.extra), 'expect', want)

    print('\n== 2. unchanged entries are byte-identical ==')
    bad = 0
    for name in no:
        if name == 'system.new.dat.br':
            continue
        a = hashlib.sha256(zo.read(name)).hexdigest()
        b = hashlib.sha256(zm.read(name)).hexdigest()
        if a != b:
            print('DIFF', name); bad += 1
    print('unchanged entries differing:', bad)

    print('\n== 3. extract + decompress modified system image ==')
    data = zm.read('system.new.dat.br')
    open(TMP_BR, 'wb').write(data)
    print('br bytes in zip:', len(data))
    subprocess.run([NODE, os.path.join(BASE, 'brotli_decompress.js'), TMP_BR, TMP_IMG], check=True)
    img_sha = sha_file(IMG); dec_sha = sha_file(TMP_IMG)
    print('system.img sha   :', img_sha)
    print('decompressed sha :', dec_sha)
    print('image match:', img_sha == dec_sha, 'size:', os.path.getsize(TMP_IMG))

    print('\n== 4. extract APK from decompressed image (inode 3297) ==')
    sys.path.insert(0, BASE)
    from ext4csum import Ext4
    e = Ext4(TMP_IMG)
    off, inode = e.read_inode(3297)
    size = struct.unpack_from('<I', inode, 4)[0] | (struct.unpack_from('<I', inode, 108)[0] << 32)
    ib = bytes(inode[40:100])
    magic, entries, maxe, depth, gen = struct.unpack_from('<HHHHI', ib, 0)
    assert magic == 0xF30A and depth == 0
    runs = []
    for i in range(entries):
        o = 12 + i * 12
        b, ln, hi, lo = struct.unpack_from('<IHHI', ib, o)
        runs.append(((hi << 32) | lo, ln))
    out = b''
    for phys, ln in runs:
        e.f.seek(phys * e.bs); out += e.f.read(ln * e.bs)
    out = out[:size]
    apk = open(APK, 'rb').read()
    print('extracted size', size, 'sha', hashlib.sha256(out).hexdigest())
    print('expected  size', len(apk), 'sha', hashlib.sha256(apk).hexdigest())
    print('APK match:', out == apk)
    e.f.close()

    print('\n== 5. transfer list / updater-script sanity ==')
    tl = zm.read('system.transfer.list').decode().splitlines()
    print('transfer.list version', tl[0], 'blocks', tl[1], 'lines', len(tl))
    assert int(tl[1]) == os.path.getsize(IMG) // 4096
    us = zm.read('META-INF/com/google/android/updater-script').decode()
    print('updater-script has system block_image_update:', 'system.new.dat.br' in us,
          'device check cm16:', 'cm16' in us)
    print('\nDONE')

if __name__ == '__main__':
    main()
