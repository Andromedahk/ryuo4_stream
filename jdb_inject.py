#!/usr/bin/env python3
"""Minimal JDWP client: inject a video URL into ASUS HomeUI's VideoView.

Attaches to com.baiyi.homeui.hshomeui (debuggable), suspends the VM, then:
  ActivityThread.currentActivityThread() -> mActivities -> valueAt(0).activity
  -> MainActivity.main_video1 -> setVideoPath(url) -> start()
Resumes and detaches.

Requires: adb forward tcp:8700 jdwp:<pid> already set up.
"""
import socket, struct, sys, time, json

HOST, PORT = '127.0.0.1', 8700
URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:18080/live.ts'

# ---------------- JDWP protocol ----------------
class JDWP:
    def __init__(self, host, port):
        self.s = socket.create_connection((host, port), timeout=10)
        self.s.settimeout(20)
        self.s.sendall(b'JDWP-Handshake')
        hs = self._recv_exact(14)
        if hs != b'JDWP-Handshake':
            raise RuntimeError('handshake failed: %r' % hs)
        self.rid = 0

    def _recv_exact(self, n):
        buf = b''
        while len(buf) < n:
            c = self.s.recv(n - len(buf))
            if not c:
                raise RuntimeError('connection closed')
            buf += c
        return buf

    def cmd(self, cs, cm, payload=b'', expect_reply=True):
        self.rid += 1
        rid = self.rid
        pkt = struct.pack('>II', len(payload) + 11, rid) + bytes([0]) + struct.pack('>BB', cs, cm) + payload
        self.s.sendall(pkt)
        if not expect_reply:
            return None
        while True:
            ln = struct.unpack('>I', self._recv_exact(4))[0]
            rid2 = struct.unpack('>I', self._recv_exact(4))[0]
            flags = self._recv_exact(1)[0]
            err = struct.unpack('>H', self._recv_exact(2))[0]
            data = self._recv_exact(ln - 11)
            if flags & 0x80:
                if rid2 != rid:
                    continue
                if err != 0:
                    raise RuntimeError('JDWP error %d for %d/%d' % (err, cs, cm))
                return data

    # helpers
    @staticmethod
    def wstr(s):
        b = s.encode('utf-8')
        return struct.pack('>I', len(b)) + b

    def rstr(self, data, off):
        n = struct.unpack('>I', data[off:off+4])[0]
        return data[off+4:off+4+n].decode('utf-8', 'replace'), off + 4 + n

    def suspend(self): self.cmd(1, 8)
    def resume(self): self.cmd(1, 9)
    def all_threads(self):
        d = self.cmd(1, 4)
        n = struct.unpack('>I', d[:4])[0]
        return [struct.unpack('>Q', d[4+i*8:12+i*8])[0] for i in range(n)]
    def classes_by_sig(self, sig):
        d = self.cmd(1, 2, self.wstr(sig))
        n = struct.unpack('>I', d[:4])[0]
        out = []
        off = 4
        for _ in range(n):
            tag = d[off]; tid = struct.unpack('>Q', d[off+1:off+9])[0]
            off += 9
            status = struct.unpack('>I', d[off:off+4])[0]; off += 4
            out.append((tid, status))
        return out
    def methods(self, refid):
        d = self.cmd(2, 5, struct.pack('>Q', refid))
        n = struct.unpack('>I', d[:4])[0]
        off = 4; out = []
        for _ in range(n):
            mid = struct.unpack('>Q', d[off:off+8])[0]; off += 8
            name, off = self.rstr(d, off)
            sig, off = self.rstr(d, off)
            mod = struct.unpack('>I', d[off:off+4])[0]; off += 4
            out.append((mid, name, sig, mod))
        return out
    def fields(self, refid):
        d = self.cmd(2, 4, struct.pack('>Q', refid))
        n = struct.unpack('>I', d[:4])[0]
        off = 4; out = []
        for _ in range(n):
            fid = struct.unpack('>Q', d[off:off+8])[0]; off += 8
            name, off = self.rstr(d, off)
            sig, off = self.rstr(d, off)
            mod = struct.unpack('>I', d[off:off+4])[0]; off += 4
            out.append((fid, name, sig, mod))
        return out
    def get_values(self, obj, fids):
        payload = struct.pack('>QI', obj, len(fids)) + b''.join(struct.pack('>Q', f) for f in fids)
        d = self.cmd(8, 2, payload)
        n = struct.unpack('>I', d[:4])[0]
        off = 4; vals = []
        for _ in range(n):
            tag = chr(d[off]); off += 1
            if tag in 'L[s':
                v = struct.unpack('>Q', d[off:off+8])[0]; off += 8
            elif tag == 'I':
                v = struct.unpack('>i', d[off:off+4])[0]; off += 4
            elif tag == 'Z':
                v = d[off]; off += 1
            elif tag == 'B':
                v = struct.unpack('>b', d[off:off+1])[0]; off += 1
            elif tag == 'C':
                v = struct.unpack('>H', d[off:off+2])[0]; off += 2
            elif tag == 'S':
                v = struct.unpack('>h', d[off:off+2])[0]; off += 2
            elif tag == 'J':
                v = struct.unpack('>q', d[off:off+8])[0]; off += 8
            elif tag == 'F':
                v = struct.unpack('>f', d[off:off+4])[0]; off += 4
            elif tag == 'D':
                v = struct.unpack('>d', d[off:off+8])[0]; off += 8
            else:
                raise RuntimeError('bad value tag %r' % tag)
            vals.append((tag, v))
        return vals
    def create_string(self, s):
        return struct.unpack('>Q', self.cmd(1, 7, self.wstr(s))[:8])[0]
    def invoke(self, obj, thread, method, args, class_invoke=False):
        payload = struct.pack('>QQQII', obj, thread, method, len(args), 0)
        for tag, v in args:
            payload += tag.encode()
            if tag in 'L[s':
                payload += struct.pack('>Q', v)
            elif tag == 'I':
                payload += struct.pack('>i', v)
        cs, cm = (3, 3) if class_invoke else (8, 6)
        d = self.cmd(cs, cm, payload)
        tag = chr(d[0]); off = 1
        if tag in 'L[s':
            ret = struct.unpack('>Q', d[off:off+8])[0]; off += 8
        elif tag == 'V':
            ret = None
        elif tag == 'I':
            ret = struct.unpack('>i', d[off:off+4])[0]; off += 4
        elif tag == 'Z':
            ret = d[off]; off += 1
        elif tag == 'J':
            ret = struct.unpack('>q', d[off:off+8])[0]; off += 8
        else:
            ret = None
        exc = struct.unpack('>Q', d[off:off+8])[0] if len(d) >= off+8 else 0
        return tag, ret, exc

def find_method(j, refid, name, sig=None):
    for mid, n, s, mod in j.methods(refid):
        if n == name and (sig is None or s == sig):
            return mid, s
    raise RuntimeError('method %s not found' % name)

def main():
    j = JDWP(HOST, PORT)
    print('[+] attached')
    j.suspend()
    print('[+] VM suspended')
    threads = j.all_threads()
    # choose thread named 'main'
    # ThreadReference.Name = 11,1
    main_thread = None
    for t in threads:
        try:
            d = j.cmd(10, 1, struct.pack('>Q', t))
            name, _ = j.rstr(d, 0)
        except Exception:
            continue
        if name == 'main':
            main_thread = t
            break
    if main_thread is None:
        main_thread = threads[0]
    print('[+] using thread', main_thread)

    at = j.classes_by_sig('Landroid/app/ActivityThread;')
    if not at:
        raise RuntimeError('ActivityThread class not found')
    at_id = at[0][0]
    cur_mid, _ = find_method(j, at_id, 'currentActivityThread', '()Landroid/app/ActivityThread;')
    tag, at_obj, exc = j.invoke(at_id, main_thread, cur_mid, [], class_invoke=True)
    print('[+] ActivityThread =', at_obj, 'exc=', exc)
    if not at_obj:
        raise RuntimeError('currentActivityThread returned null')

    # mActivities field
    fields = {n: (f, s) for f, n, s, m in j.fields(at_id)}
    fid = fields['mActivities'][0]
    vals = j.get_values(at_obj, [fid])
    map_obj = vals[0][1]
    print('[+] mActivities =', map_obj)

    # ArrayMap.valueAt(int) -> Object
    amap = j.classes_by_sig('Landroid/util/ArrayMap;')[0][0]
    va_mid, _ = find_method(j, amap, 'valueAt', '(I)Ljava/lang/Object;')
    tag, rec, exc = j.invoke(map_obj, main_thread, va_mid, [('I', 0)])
    print('[+] ActivityClientRecord =', rec, 'exc=', exc)

    # ActivityClientRecord.activity field
    rec_cls = j.classes_by_sig('Landroid/app/ActivityThread$ActivityClientRecord;')[0][0]
    rf = {n: (f, s) for f, n, s, m in j.fields(rec_cls)}
    act_fid = rf['activity'][0]
    act = j.get_values(rec, [act_fid])[0][1]
    print('[+] activity =', act)

    # MainActivity.main_video1 field
    ma = j.classes_by_sig('Lcom/baiyi/homeui/hshomeui/MainActivity;')[0][0]
    mf = {n: (f, s) for f, n, s, m in j.fields(ma)}
    vv_fid = mf['main_video1'][0]
    vv = j.get_values(act, [vv_fid])[0][1]
    print('[+] main_video1 =', vv)

    # VideoView.setVideoPath(String) then start()
    vv_cls = j.classes_by_sig('Lcom/baiyi/homeui/hshomeui/FullScreenVideoView;')[0][0]
    try:
        svp_mid, _ = find_method(j, vv_cls, 'setVideoPath', '(Ljava/lang/String;)V')
    except Exception:
        vvw = j.classes_by_sig('Landroid/widget/VideoView;')[0][0]
        svp_mid, _ = find_method(j, vvw, 'setVideoPath', '(Ljava/lang/String;)V')
    start_mid, _ = find_method(j, vv_cls, 'start', '()V')
    sid = j.create_string(URL)
    print('[+] url string id', sid)
    tag, ret, exc = j.invoke(vv, main_thread, svp_mid, [('L', sid)])
    print('[+] setVideoPath ->', tag, 'exc=', exc)
    time.sleep(0.3)
    tag, ret, exc = j.invoke(vv, main_thread, start_mid, [])
    print('[+] start ->', tag, 'exc=', exc)

    j.resume()
    print('[+] resumed; done')
    try:
        j.s.close()
    except Exception:
        pass

if __name__ == '__main__':
    main()


