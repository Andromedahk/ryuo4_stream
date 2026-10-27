import re
p = r"D:\ROG longwang4\host-re\jsc_strings.txt"
ss = [l.rstrip('\n') for l in open(p, encoding='utf-8', errors='replace')]
print("strings:", len(ss))
groups = {
 'frame': r'frame|Frame',
 'protocol': r'Ack|Seq|ContentType|ContentLength|Header|header',
 'hid': r'\bhid\b|HID|report|Report|usage|Usage',
 'media': r'media|Media|push|Push|pcMedia|Preset',
 'cmd': r'cmd|Cmd|CMD|command|Command',
 'video': r'video|Video|codec|decode|encode|ffmpeg|gif|GIF|mp4|MP4|png|PNG',
 'usb': r'usb|USB|serial|Serial|port|Port',
 'err': r'invalid|incomplete|checkSum|checksum|checksum|timeout|Timeout',
}
for name, pat in groups.items():
    r = re.compile(pat)
    hits = [s for s in ss if r.search(s) and len(s) < 300]
    print("\n##### ", name, len(hits))
    seen=set()
    for s in hits:
        if s in seen: continue
        seen.add(s)
        print("  ", s)
        if len(seen)>=60: break
