import re, glob, os
logdir = r"C:\Users\ZZZX\AppData\Roaming\rog_infohub\logs"
pats = ['Message Frame','hid device send','HID send','send to conn','hid send','write data','AckNumber','SeqNumber','recive data','hid device write','cmd: ','other cmd']
for f in sorted(glob.glob(os.path.join(logdir,'*.log')))[:4]:
    print("="*25, os.path.basename(f), os.path.getsize(f))
    with open(f, encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()
    show = 0
    for i, ln in enumerate(lines):
        if any(p in ln for p in ['Message Frame','hid device recive data','hid device send','HID send','cmd: ','other cmd','recive data']):
            ctx = ''.join(lines[i:i+3])
            print(ctx[:1200].rstrip())
            show += 1
            if show > 40: break
