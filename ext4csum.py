#!/usr/bin/env python3
"""ext4 helpers: read/write inode fields and metadata_csum (crc32c) checksums.
Verified against unmodified inodes before use.
"""
import struct

CRC32C_POLY = 0x82F63B78

def crc32c(crc, data):
    crc ^= 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ CRC32C_POLY
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF

class Ext4:
    def __init__(self, path):
        self.f = open(path, 'r+b')
        self.path = path
        sb = self.read(1024, 1024)
        self.sb = sb
        self.magic = struct.unpack_from('<H', sb, 56)[0]
        assert self.magic == 0xEF53, 'not ext4'
        self.inodes_count = struct.unpack_from('<I', sb, 0)[0]
        self.blocks_count = struct.unpack_from('<I', sb, 4)[0] | (struct.unpack_from('<I', sb, 0x150)[0] << 32)
        self.first_data_block = struct.unpack_from('<I', sb, 20)[0]
        self.log_block_size = struct.unpack_from('<I', sb, 24)[0]
        self.bs = 1024 << self.log_block_size
        self.blocks_per_group = struct.unpack_from('<I', sb, 32)[0]
        self.inodes_per_group = struct.unpack_from('<I', sb, 40)[0]
        self.inode_size = struct.unpack_from('<H', sb, 88)[0]
        self.desc_size = struct.unpack_from('<H', sb, 254)[0] or 32
        self.feature_compat = struct.unpack_from('<I', sb, 0x5C)[0]
        self.feature_incompat = struct.unpack_from('<I', sb, 0x60)[0]
        self.feature_ro_compat = struct.unpack_from('<I', sb, 0x64)[0]
        self.uuid = sb[0x68:0x78]
        self.checksum_seed = struct.unpack_from('<I', sb, 0x270)[0] if len(sb) > 0x274 else 0
        self.metadata_csum = bool(self.feature_ro_compat & 0x0400)
        self.metadata_csum_seed = bool(self.feature_incompat & 0x2000)
        gdt_off = (self.first_data_block + 1) * self.bs
        self.gdt_off = gdt_off

    def read(self, off, n):
        self.f.seek(off)
        return self.f.read(n)

    def write(self, off, data):
        self.f.seek(off); self.f.write(data)

    def inode_offset(self, ino):
        grp = (ino - 1) // self.inodes_per_group
        idx = (ino - 1) % self.inodes_per_group
        gd = self.read(self.gdt_off + grp * self.desc_size, self.desc_size)
        itable = struct.unpack_from('<I', gd, 8)[0]
        if self.desc_size > 32:
            itable |= struct.unpack_from('<H', gd, 0x28)[0] << 32
        return itable * self.bs + idx * self.inode_size

    def read_inode(self, ino):
        off = self.inode_offset(ino)
        return off, bytearray(self.read(off, self.inode_size))

    def inode_seed(self, ino, generation):
        if self.metadata_csum_seed:
            crc = self.checksum_seed
        else:
            crc = crc32c(0xFFFFFFFF, self.uuid)
        crc = crc32c(crc, struct.pack('<I', ino & 0xFFFFFFFF))
        crc = crc32c(crc, struct.pack('<I', generation))
        return crc

    def inode_checksum(self, ino, inode):
        gen = struct.unpack_from('<I', inode, 0x64)[0]
        extra_isize = struct.unpack_from('<H', inode, 0x80)[0] if self.inode_size > 128 else 0
        crc = self.inode_seed(ino, gen)
        # checksum_lo at 0x7C (2 bytes), checksum_hi at 0x82 (2 bytes) when extra inode exists
        has_hi = self.inode_size > 128 and extra_isize >= 0x24
        crc = crc32c(crc, bytes(inode[0:0x7C]))
        if self.inode_size > 128:
            if has_hi:
                crc = crc32c(crc, bytes(inode[0x7E:0x82]))
                crc = crc32c(crc, bytes(inode[0x84:self.inode_size]))
            else:
                crc = crc32c(crc, bytes(inode[0x7E:self.inode_size]))
        crc = crc32c(crc, b'\x00\x00')  # checksum_lo placeholder contribution is zeroed
        return crc & 0xFFFF

    def get_checksum_stored(self, inode):
        lo = struct.unpack_from('<H', inode, 0x7C)[0]
        hi = struct.unpack_from('<H', inode, 0x82)[0] if self.inode_size > 128 else 0
        return lo, hi

    def inode_checksum2(self, ino, inode):
        """Kernel algorithm: checksum_lo/hi fields are treated as zero and skipped."""
        gen = struct.unpack_from('<I', inode, 0x64)[0]
        extra_isize = struct.unpack_from('<H', inode, 0x80)[0] if self.inode_size > 128 else 0
        crc = self.inode_seed(ino, gen)
        if self.inode_size > 128:
            if extra_isize >= 0x24:
                crc = crc32c(crc, bytes(inode[0:0x7C]))
                crc = crc32c(crc, b'\x00\x00')
                crc = crc32c(crc, bytes(inode[0x7E:0x82]))
                crc = crc32c(crc, b'\x00\x00')
                crc = crc32c(crc, bytes(inode[0x84:self.inode_size]))
            else:
                crc = crc32c(crc, bytes(inode[0:0x7C]))
                crc = crc32c(crc, b'\x00\x00')
                crc = crc32c(crc, bytes(inode[0x7E:self.inode_size]))
        else:
            crc = crc32c(crc, bytes(inode[0:0x7C]))
            crc = crc32c(crc, b'\x00\x00')
            crc = crc32c(crc, bytes(inode[0x7E:128]))
        return crc & 0xFFFF
