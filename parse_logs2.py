import re, glob, os
logdir = r"C:\Users\ZZZX\AppData\Roaming\rog_infohub\logs"
pat = re.compile(r'pushMedia|pushFile|ffmpeg|pcMedia|MediaStation|adbExec|adb push|mediaFrame|CatchVideo|frame |hid|HID|4244|reverse|forward|shell|am start|screenrecord|/sdcard|resolution|bitrate|fps|codec|videoStream', re.I)
for f in sorted(glob.glob(os.path.join(logdir,'*.log'))):
    size = os.path.getsize(f)
    print("="*20, os.path.basename(f), size)
    if size > 20_000_000:
        # stream line by line
        pass
    n=0
    try:
        with open(f, encoding='utf-8', errors='replace') as fh:
            for ln in fh:
                if pat.search(ln):
                    print(ln.rstrip()[:500]); n+=1
                    if n>=80: break
    except Exception as e:
        print("ERR", e)
