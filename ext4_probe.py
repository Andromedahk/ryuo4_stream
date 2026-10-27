import struct, os, sys
IMG=r"D:\ROG longwang4\firmware\unpacked\system.new.dat"
BS=4096
f=open(IMG,'rb')
sb=f.read(1024)
assert len(sb)==1024
(f.seek(1024)); sb=f.read(1024)
magic=struct.unpack_from('<H',sb,56)[0]
print('magic',hex(magic))
ino_count=struct.unpack_from('<I',sb,0)[0]
blocks_lo=struct.unpack_from('<I',sb,4)[0]
first_data=struct.unpack_from('<I',sb,20)[0]
log_bs=struct.unpack_from('<I',sb,24)[0]
blocks_per_group=struct.unpack_from('<I',sb,32)[0]
inodes_per_group=struct.unpack_from('<I',sb,40)[0]
inode_size=struct.unpack_from('<H',sb,88)[0]
desc_size=struct.unpack_from('<H',sb,254)[0]
blocks_hi=struct.unpack_from('<I',sb,0x150)[0]
print('inodes',ino_count,'blocks',blocks_lo,blocks_hi,'bs',1024<<log_bs,'inode_size',inode_size,'ipg',inodes_per_group,'bpg',blocks_per_group,'desc_size',desc_size,'first_data',first_data)
logical_bs=1024<<log_bs
# GDT at block (first_data+1)
gdt_off=(first_data+1)*logical_bs
ino=3297
grp=(ino-1)//inodes_per_group
idx=(ino-1)%inodes_per_group
f.seek(gdt_off + grp*(desc_size or 32))
gd=f.read(desc_size or 32)
itable_lo=struct.unpack_from('<I',gd,8)[0]
itable_hi=struct.unpack_from('<H',gd,0x28)[0] if (desc_size or 32)>32 else 0
itable=itable_lo | (itable_hi<<32)
print('group',grp,'idx',idx,'itable',itable)
inoff=itable*logical_bs + idx*inode_size
f.seek(inoff); inode=f.read(inode_size)
mode=struct.unpack_from('<H',inode,0)[0]
size_lo=struct.unpack_from('<I',inode,4)[0]
flags=struct.unpack_from('<I',inode,32)[0]
size_hi=struct.unpack_from('<I',inode,108)[0]
size=size_lo | (size_hi<<32)
print('mode',oct(mode),'size',size,'flags',hex(flags),'extents',bool(flags & 0x80000))
# parse extent tree in i_block
ib=inode[40:100]
magic,entries,maxe,depth,gen=struct.unpack_from('<HHHHI',ib,0)
print('eh magic',hex(magic),'entries',entries,'max',maxe,'depth',depth)
def parse_extents(node, depth):
    magic,entries,maxe,d=depth
PY
