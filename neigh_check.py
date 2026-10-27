import sys, struct
sys.path.insert(0,r"D:\ROG longwang4")
from ext4csum import Ext4
e=Ext4(r"D:\ROG longwang4\firmware-build\system.img")
print('image blocks',e.blocks_count,'size',e.blocks_count*e.bs)
for ino in (3295,3296,3297,3298,3299,3300):
    try:
        off,inode=e.read_inode(ino)
        size=struct.unpack_from('<I',inode,4)[0]|(struct.unpack_from('<I',inode,108)[0]<<32)
        flags=struct.unpack_from('<I',inode,32)[0]
        runs=[]
        if flags & 0x80000:
            ib=bytes(inode[40:100]); magic,entries,maxe,depth,gen=struct.unpack_from('<HHHHI',ib,0)
            for i in range(entries):
                o=12+i*12
                if depth==0:
                    b,ln,hi,lo=struct.unpack_from('<IHHI',ib,o); runs.append(((hi<<32)|lo,ln))
        print(ino,'size',size,'runs',runs)
    except Exception as ex: print(ino,'ERR',ex)
