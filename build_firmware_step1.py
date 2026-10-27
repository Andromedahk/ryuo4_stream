#!/usr/bin/env python3
"""Build a modified ROG RYUO IV system ext4 image that preinstalls the
low-latency streaming player (com.ryuo.stream) as a system app.

Strategy: the system partition is 100% full, so instead of adding files we
replace the content of an unused, non-critical system APK in place, keeping the
ext4 inode/metadata untouched:

    /system/priv-app/SharedStorageBackup/SharedStorageBackup.apk  (16,798 B)
        -> our APK padded with zeros to the same size

Because the file size and its allocated extents do not change, no ext4 metadata
(inode bitmap, block bitmap, group descriptors, inode checksums) needs to be
rewritten.  The resulting APK is still a valid ZIP (only 19 bytes of zero
padding after the EOCD).
"""
import struct, os, shutil, hashlib, sys, zipfile

BASE = r"D:\ROG longwang4"
SRC_IMG = os.path.join(BASE, r"firmware\unpacked\system.new.dat")
OUT_DIR = os.path.join(BASE, "firmware-build")
OUT_IMG = os.path.join(OUT_DIR, "system.img")
APK = os.path.join(BASE, r"exe\ryuo-stream.apk")   # v1+v2+v3 signed copy
TARGET_SIZE = 16798
TARGET_INO = 3297                                   # SharedStorageBackup.apk

BS = 4096

def ext4_extents(f, inode_off, inode_size):
    f.seek(inode_off)
    inode = f.read(inode_size)
    flags = struct.unpack_from('<I', inode, 32)[0]
    if not (flags & 0x80000):
        raise SystemExit('target inode is not extent-based')
    ib = inode[40:100]
    magic, entries, maxe, depth, gen = struct.unpack_from('<HHHHI', ib, 0)
    if magic != 0xF30A:
        raise SystemExit('bad extent header')
    runs = []
    def walk(node, depth):
        magic, entries, maxe, d, gen = struct.unpack_from('<HHHHI', node, 0)
        for i in range(entries):
            off = 12 + i * 12
            if d == 0:
                ee_block, ee_len, hi, lo = struct.unpack_from('<IHHI', node, off)
                runs.append((ee_block, ee_len, (hi << 32) | lo))
            else:
                ei_block, leaf_lo, leaf_hi, unused = struct.unpack_from('<IIHH', node, off)
                leaf = (leaf_hi << 32) | leaf_lo
                f.seek(leaf * BS)
                walk(f.read(BS), d - 1)
    walk(ib, depth)
    return sorted(runs)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    apk = open(APK, 'rb').read()
    if len(apk) > TARGET_SIZE:
        raise SystemExit('APK is larger than target file')
    padded = apk + b'\x00' * (TARGET_SIZE - len(apk))
    print('APK %d bytes -> padded to %d (+%d zero bytes)' % (len(apk), len(padded), TARGET_SIZE - len(apk)))

    shutil.copyfile(SRC_IMG, OUT_IMG)
    f = open(OUT_IMG, 'r+b')
    sb = f.read(1024); f.seek(1024); sb = f.read(1024)
    inodes_per_group = struct.unpack_from('<I', sb, 40)[0]
    inode_size = struct.unpack_from('<H', sb, 88)[0]
    first_data = struct.unpack_from('<I', sb, 20)[0]
    log_bs = struct.unpack_from('<I', sb, 24)[0]
    bs = 1024 << log_bs
    desc_size = struct.unpack_from('<H', sb, 254)[0] or 32
    grp = (TARGET_INO - 1) // inodes_per_group
    idx = (TARGET_INO - 1) % inodes_per_group
    f.seek((first_data + 1) * bs + grp * desc_size)
    gd = f.read(desc_size)
    itable_lo = struct.unpack_from('<I', gd, 8)[0]
    itable_hi = struct.unpack_from('<H', gd, 0x28)[0] if desc_size > 32 else 0
    itable = itable_lo | (itable_hi << 32)
    inode_off = itable * bs + idx * inode_size
    f.seek(inode_off); inode = f.read(inode_size)
    size = struct.unpack_from('<I', inode, 4)[0] | (struct.unpack_from('<I', inode, 108)[0] << 32)
    if size != TARGET_SIZE:
        raise SystemExit('target size mismatch: inode says %d' % size)
    runs = ext4_extents(f, inode_off, inode_size)
    total = sum(l for _, l, _ in runs) * bs
    print('inode %d extents: %r  logical capacity %d bytes' % (TARGET_INO, runs, total))
    if total < TARGET_SIZE:
        raise SystemExit('extent capacity too small')

    pos = 0
    for logical, length, physical in runs:
        n = min(length * bs, len(padded) - pos)
        if n <= 0:
            break
        f.seek(physical * bs)
        f.write(padded[pos:pos + n])
        pos += n
    f.flush(); os.fsync(f.fileno()); f.close()
    print('wrote %d / %d bytes into image' % (pos, len(padded)))

    # ---- verify read-back ----
    f = open(OUT_IMG, 'rb')
    head = f.read(1024); f.seek(1024); sb = f.read(1024)
    grp = (TARGET_INO - 1) // inodes_per_group
    idx = (TARGET_INO - 1) % inodes_per_group
    f.seek((first_data + 1) * bs + grp * desc_size)
    gd = f.read(desc_size)
    itable = struct.unpack_from('<I', gd, 8)[0]
    inode_off = itable * bs + idx * inode_size
    runs = ext4_extents(f, inode_off, inode_size)
    f.seek(inode_off); inode = f.read(inode_size)
    size = struct.unpack_from('<I', inode, 4)[0] | (struct.unpack_from('<I', inode, 108)[0] << 32)
    data = b''
    for logical, length, physical in runs:
        f.seek(physical * bs)
        data += f.read(length * bs)
    data = data[:size]
    f.close()
    if data != padded:
        raise SystemExit('read-back mismatch!')
    print('read-back OK: %d bytes, sha256 %s' % (len(data), hashlib.sha256(data).hexdigest()))
    open(os.path.join(OUT_DIR, 'extracted_apk.bin'), 'wb').write(data)
    # zip sanity on padded apk
    try:
        z = zipfile.ZipFile(os.path.join(OUT_DIR, 'extracted_apk.bin'))
        print('zip entries:', z.namelist())
        print('zip test:', z.testzip())
    except Exception as e:
        print('ZIP PARSE WARNING:', e)

if __name__ == '__main__':
    main()
