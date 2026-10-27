import struct, json, os
base=r"D:\ROG longwang4\firmware\extracted"
tl=open(os.path.join(base,'system.transfer.list'),'rb').read().decode()
lines=tl.splitlines()
print('lines',len(lines),'first5',lines[:5],'last3',lines[-3:])
blk=4096
sz=os.path.getsize(r"D:\ROG longwang4\firmware\unpacked\system.new.dat")
print('image size',sz,'blocks',sz/blk)
# parse commands
cov={}
for ln in lines[4:]:
    if not ln.strip(): continue
    if ln.startswith('new '):
        nums=[int(x) for x in ln[4:].split(',')]
        print('sample new line nums',nums[:6])
        break
# coverage test assuming pairs after first number
ranges=[]
for ln in lines[4:]:
    ln=ln.strip()
    if not ln: continue
    if ln.startswith('new '):
        nums=[int(x) for x in ln[4:].split(',')]
        # hypothesis: nums[0]=count, then pairs start,len
        cnt=nums[0]; pairs=nums[1:]
        assert len(pairs)==cnt*2 or True
        for i in range(0,len(pairs),2):
            ranges.append((pairs[i],pairs[i+1]))
        if len(pairs)!=cnt*2:
            pass
    else:
        print('other cmd:',ln[:50])
print('ranges',len(ranges),'first',ranges[:3],'last',ranges[-3:])
# coverage
ranges_sorted=sorted(ranges)
pos=0; gaps=[]
for s,l in ranges_sorted:
    if s>pos: gaps.append((pos,s))
    elif s<pos: print('overlap',s,l,pos)
    pos=max(pos,s+l)
print('covered to',pos,'gaps',gaps[:5],'gapcount',len(gaps))
