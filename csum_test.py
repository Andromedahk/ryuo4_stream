import sys
sys.path.insert(0,r"D:\ROG longwang4")
from ext4csum import Ext4
e=Ext4(r"D:\ROG longwang4\firmware\unpacked\system.new.dat")
print('bs',e.bs,'inode_size',e.inode_size,'metadata_csum',e.metadata_csum,'csum_seed',e.metadata_csum_seed)
print('compat',hex(e.feature_compat),'incompat',hex(e.feature_incompat),'ro_compat',hex(e.feature_ro_compat))
for ino in (3297, 3221, 14, 908):
    off, inode = e.read_inode(ino)
    lo,hi=e.get_checksum_stored(inode)
    c1=e.inode_checksum(ino,inode)
    c2=e.inode_checksum2(ino,inode)
    print('ino',ino,'off',off,'stored',hex(lo),hex(hi),'calc1',hex(c1),'calc2',hex(c2),'extra_isize',hex(int.from_bytes(inode[0x80:0x82],'little')))
