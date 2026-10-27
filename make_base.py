#!/usr/bin/env python3
"""Prototype: stream into a preallocated CBR MPEG-TS file that the stock
HomeUI player reads sequentially (overwrite bytes ahead of the read pointer).

Slot size = 565248 bytes = 138 * 4096 (dd block aligned), 1 second of video.
"""
import os, subprocess, sys, struct

FF = r"C:\Program Files\ASUS Info Hub - ROG RYUO IV\bin\ffmpeg.exe"
OUT = r"D:\ROG longwang4\stream_test"
SLOT = 565248
N = 20

NULL = bytes([0x47, 0x1F, 0xFF, 0x10]) + b'\xFF' * 184

def make_chunk(path, seconds, pts, lavfi, extra=()):
    args = [FF, '-hide_banner', '-y', '-loglevel', 'error',
            '-f', 'lavfi', '-i', lavfi, '-t', str(seconds),
            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p', '-b:v', '3000k', '-maxrate', '3000k',
            '-bufsize', '1500k', '-g', '30', '-muxrate', '4521984',
            '-output_ts_offset', str(pts), '-f', 'mpegts', path]
    args.extend(extra)
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[-500:])
    data = open(path, 'rb').read()
    return data

def pad_to(data, size):
    if len(data) > size:
        # keep whole 188-byte packets up to size
        n = size // 188
        return data[:n * 188]
    n = (size - len(data)) // 188
    return data + NULL * n

def main():
    os.makedirs(OUT, exist_ok=True)
    base_parts = []
    for k in range(N):
        raw = make_chunk(os.path.join(OUT, 'c%02d.ts' % k), 1, k,
                         'testsrc2=size=1920x960:rate=30')
        part = pad_to(raw, SLOT)
        print('slot %d raw %d -> %d' % (k, len(raw), len(part)))
        base_parts.append(part)
    base = b''.join(base_parts)
    open(os.path.join(OUT, 'base_slots.ts'), 'wb').write(base)
    print('base size', len(base), 'expected', SLOT * N)
    # red replacement slots with matching PTS
    for k in (10, 11):
        raw = make_chunk(os.path.join(OUT, 'red%02d.ts' % k), 1, k,
                         'color=red:size=1920x960:rate=30')
        part = pad_to(raw, SLOT)
        open(os.path.join(OUT, 'red_slot%02d.bin' % k), 'wb').write(part)
        print('red slot %d padded %d' % (k, len(part)))

if __name__ == '__main__':
    main()
