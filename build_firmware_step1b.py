#!/usr/bin/env python3
"""Inject the streaming player APK into the ROG RYUO IV system ext4 image.

The system partition is 100% full, but the image has no metadata_csum, so we can
safely replace an unused system APK in place (same extents) and update the inode
size to the new APK's real length:

    /system/priv-app/SharedStorageBackup/SharedStorageBackup.apk (ino 3297)
        -> ryuo-stream.apk (com.ryuo.stream), size 16,779 B

No block/inode bitmap, group descriptor or checksum changes are needed.
"""
import struct, os, shutil, hashlib, zipfile

BASE = r"D:\ROG longwang4"
SRC_IMG = os.path.join(BASE, r"firmware\unpacked\system.new.dat")
OUT_DIR = os.path.join(BASE, "firmware-build")
OUT_IMG = os.path.join(OUT_DIR, "system.img")
APK = os.path.join(BASE, r"apk\ryuo-stream-v2.apk")
TARGET_INO = 3297

BS = 4096

def inode_info(f):
    f.seek(1024); sb = f.read(1024)
    assert struct.unpack_from('<H', sb, 56)[0] == 0xEF53
    ipg = struct.unpack_from('<I', sb, 40)[0]
    isz = struct.unpack_from('<H', sb, 88)[0]
    first = struct.unpack_from('<I', sb, 20)[0]
    bs = 1024 << struct.unpack_from('<I', sb, 24)[0]
    dsz = struct.unpack_from('<H', sb, 254)[0] or 32
    grp = (TARGET_INO - 1) // ipg
    idx = (TARGET_INO - 1) % ipg
    f.seek((first + 1) * bs + grp * dsz)
    gd = f.read(dsz)
    itable = struct.unpack_from('<I', gd, 8)[0]
    if dsz > 32:
        itable |= struct.unpack_from('<H', gd, 0x28)[0] << 32
    off = itable * bs + idx * isz
    f.seek(off)
    inode = bytearray(f.read(isz))
    return off, inode, isz

def parse_extents(inode, bs):
    flags = struct.unpack_from('<I', inode, 32)[0]
    assert flags & 0x80000, 'not extent based'
    ib = bytes(inode[40:100])
    magic, entries, maxe, depth, gen = struct.unpack_from('<HHHHI', ib, 0)
    assert magic == 0xF30A
    runs = []
    def walk(node, d):
        magic, entries, maxe, depth2, gen = struct.unpack_from('<HHHHI', node, 0)
        for i in range(entries):
            o = 12 + i * 12
            if d == 0:
                b, ln, hi, lo = struct.unpack_from('<IHHI', node, o)
                runs.append((b, ln, (hi << 32) | lo))
            else:
                _, leaf_lo, leaf_hi, _ = struct.unpack_from('<IIHH', node, o)
                raise SystemExit('extent tree depth > 0 not supported')
    walk(ib, depth)
    return sorted(runs)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    apk = open(APK, 'rb').read()
    print('APK %s: %d bytes sha256 %s' % (APK, len(apk), hashlib.sha256(apk).hexdigest()))
    shutil.copyfile(SRC_IMG, OUT_IMG)
    f = open(OUT_IMG, 'r+b')
    off, inode, isz = inode_info(f)
    old_size = struct.unpack_from('<I', inode, 4)[0] | (struct.unpack_from('<I', inode, 108)[0] << 32)
    print('inode %d @0x%x size %d' % (TARGET_INO, off, old_size))
    runs = parse_extents(inode, BS)
    capacity = sum(l for _, l, _ in runs) * BS
    print('extents', runs, 'capacity', capacity)
    if len(apk) > capacity:
        raise SystemExit('APK too large for extents')
    # write content
    pos = 0
    for logical, length, phys in runs:
        n = min(length * BS, len(apk) - pos)
        if n <= 0:
            break
        f.seek(phys * BS)
        f.write(apk[pos:pos + n])
        pos += n
    # zero the rest of the allocated blocks (clean)
    for logical, length, phys in runs:
        start = pos if pos > logical * BS else logical * BS
        if length * BS > (pos - logical * BS):
            pass
    # update inode size
    struct.pack_into('<I', inode, 4, len(apk) & 0xFFFFFFFF)
    struct.pack_into('<I', inode, 108, len(apk) >> 32)
    f.seek(off)
    f.write(inode)
    f.flush(); os.fsync(f.fileno()); f.close()
    print('patched %d bytes' % len(apk))

    # verify
    f = open(OUT_IMG, 'rb')
    off2, inode2, _ = inode_info(f)
    size2 = struct.unpack_from('<I', inode2, 4)[0] | (struct.unpack_from('<I', inode2, 108)[0] << 32)
    runs2 = parse_extents(inode2, BS)
    data = b''
    for logical, length, phys in runs2:
        f.seek(phys * BS)
        data += f.read(length * BS)
    data = data[:size2]
    f.close()
    assert size2 == len(apk), (size2, len(apk))
    assert data == apk, 'read-back mismatch'
    print('read-back OK: %d bytes' % size2)
    open(os.path.join(OUT_DIR, 'extracted_apk.apk'), 'wb').write(data)
    z = zipfile.ZipFile(os.path.join(OUT_DIR, 'extracted_apk.apk'))
    print('zip entries:', z.namelist(), 'test:', z.testzip())

if __name__ == '__main__':
    main()
