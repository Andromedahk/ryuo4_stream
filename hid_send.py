#!/usr/bin/env python3
"""Send a host->device HID frame to the ROG RYUO IV screen (VID 0B05 PID 1C76).

Frame format (reverse engineered):
    [0x5A][total_len_hi][total_len_lo][ASCII payload][checksum][0x5A]
    total_len = 5 + len(ASCII payload)
    checksum  = (sum(total_len bytes) + sum(ASCII payload)) & 0xFF

The screen's SerialService reads 1024-byte HID OUT reports and dispatches
"POST <cmd> <ver>" messages to HomeUI.  A "POST config 1" message carries the
waterBlockScreen JSON (media playlist, brightness, ...).

Usage:
  python hid_send.py probe
  python hid_send.py conn
  python hid_send.py config <json-file>
  python hid_send.py config-url <url>
"""
import ctypes, ctypes.wintypes as wt, struct, sys, json, time

# ---------------------------------------------------------------- win32 ---
setupapi = ctypes.WinDLL('setupapi')
hid = ctypes.WinDLL('hid')
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

GUID_DEVINTERFACE_HID = (ctypes.c_ubyte * 16)(
    0xB2, 0x55, 0x1E, 0x4D, 0x6F, 0xF1, 0xCF, 0x11,
    0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30)
DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('InterfaceClassGuid', ctypes.c_ubyte * 16),
                ('Flags', wt.DWORD), ('Reserved', ctypes.c_void_p)]

class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('DevicePath', ctypes.c_wchar * 1024)]

class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [('Size', wt.ULONG), ('VendorID', wt.USHORT),
                ('ProductID', wt.USHORT), ('VersionNumber', wt.USHORT)]

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [('Usage', wt.USHORT), ('UsagePage', wt.USHORT),
                ('InputReportByteLength', wt.USHORT), ('OutputReportByteLength', wt.USHORT),
                ('FeatureReportByteLength', wt.USHORT), ('Reserved', wt.USHORT * 17),
                ('NumberLinkCollectionNodes', wt.USHORT), ('NumberInputButtonCaps', wt.USHORT),
                ('NumberInputValueCaps', wt.USHORT), ('NumberInputDataIndices', wt.USHORT),
                ('NumberOutputButtonCaps', wt.USHORT), ('NumberOutputValueCaps', wt.USHORT),
                ('NumberOutputDataIndices', wt.USHORT), ('NumberFeatureButtonCaps', wt.USHORT),
                ('NumberFeatureValueCaps', wt.USHORT), ('NumberFeatureDataIndices', wt.USHORT)]

setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, wt.HWND, wt.DWORD]
setupapi.SetupDiGetClassDevsW.restype = wt.HANDLE
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
setupapi.SetupDiEnumDeviceInterfaces.restype = wt.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wt.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = wt.BOOL
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
kernel32.CreateFileW.restype = wt.HANDLE
kernel32.WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
kernel32.WriteFile.restype = wt.BOOL
hid.HidD_GetAttributes.argtypes = [wt.HANDLE, ctypes.c_void_p]
hid.HidD_GetAttributes.restype = wt.BOOL
hid.HidD_GetPreparsedData.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wt.BOOL
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
hid.HidP_GetCaps.restype = wt.ULONG
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wt.BOOL

def find_devices():
    out = []
    h = setupapi.SetupDiGetClassDevsW(ctypes.byref(GUID_DEVINTERFACE_HID), None, None,
                                      DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if h == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    i = 0
    while True:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(did)
        if not setupapi.SetupDiEnumDeviceInterfaces(h, None, ctypes.byref(GUID_DEVINTERFACE_HID), i, ctypes.byref(did)):
            break
        i += 1
        need = wt.DWORD(0)
        setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(did), None, 0, ctypes.byref(need), None)
        if need.value == 0:
            continue
        buf = ctypes.create_string_buffer(need.value)
        detail = ctypes.cast(buf, ctypes.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W))
        detail.contents.cbSize = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        if not setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(did), detail, need, ctypes.byref(need), None):
            continue
        path = detail.contents.DevicePath
        hd = kernel32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                                  FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
        if hd == INVALID_HANDLE_VALUE:
            continue
        attrs = HIDD_ATTRIBUTES(); attrs.Size = ctypes.sizeof(attrs)
        hid.HidD_GetAttributes(hd, ctypes.byref(attrs))
        pp = ctypes.c_void_p()
        caps = HIDP_CAPS()
        if hid.HidD_GetPreparsedData(hd, ctypes.byref(pp)):
            hid.HidP_GetCaps(pp, ctypes.byref(caps))
            hid.HidD_FreePreparsedData(pp)
        else:
            caps.UsagePage = 0; caps.OutputReportByteLength = 0
        out.append(dict(path=path, handle=hd, vid=attrs.VendorID, pid=attrs.ProductID,
                        usage_page=caps.UsagePage, usage=caps.Usage,
                        out_len=caps.OutputReportByteLength))
    setupapi.SetupDiDestroyDeviceInfoList(h)
    return out

# ------------------------------------------------------------- protocol ---
def build_frame(cmd, version, headers, body=b''):
    payload = ('POST %s %s\r\n' % (cmd, version)).encode()
    for k, v in headers:
        payload += ('%s=%s\r\n' % (k, v)).encode()
    payload += b'\r\n' + body
    total = 5 + len(payload)
    head = bytes([0x5A]) + struct.pack('>H', total)
    chk = (sum(head[1:]) + sum(payload)) & 0xFF
    return head + payload + bytes([chk, 0x5A])

def send_frame(dev, frame):
    n = dev['out_len'] or 1024
    if len(frame) > n:
        raise ValueError('frame %d > report %d' % (len(frame), n))
    buf = b'\x00' + frame  # report ID 0 prefix (OutputReportByteLength=1025)
    buf = buf + b'\x00' * (n - len(buf))
    written = wt.DWORD(0)
    ok = kernel32.WriteFile(dev['handle'], buf, len(buf), ctypes.byref(written), None)
    err = ctypes.get_last_error()
    return bool(ok), written.value, err

def pick_target(devs):
    cands = [d for d in devs if d['vid'] == 0x0B05 and d['pid'] == 0x1C76]
    if not cands:
        raise SystemExit('no 0B05:1C76 HID device found; devices: %r' % [(hex(d['vid']), hex(d['pid'])) for d in devs])
    # prefer vendor-defined usage page 0xFF00
    cands.sort(key=lambda d: 0 if d['usage_page'] == 0xFF00 else 1)
    return cands[0]

def next_seq():
    return int(time.time() * 1000) & 0x7FFFFFFF

def send_post(dev, cmd, headers, body=b''):
    h = [('SeqNumber', str(next_seq())), ('Date', str(int(time.time() * 1000))),
         ('ContentType', 'json'), ('ContentLength', str(len(body)))]
    frame = build_frame(cmd, '1', h, body)
    ok, written, err = send_frame(dev, frame)
    print('frame len=%d total_field=%d checksum=0x%02x write_ok=%s written=%d err=%d'
          % (len(frame), struct.unpack('>H', frame[1:3])[0], frame[-2], ok, written, err))
    return ok

DEFAULT_JSON = {
    "temperature": "Celsius",
    "waterBlockScreen": {
        "enable": True, "displayInSleep": True, "brightness": 85,
        "id": {"id": "Customization", "screenMode": "Full Screen", "playMode": "Single",
               "media": ["http://127.0.0.1:18080/live.ts"],
               "settings": {"titleColor": "#E5252B", "contentColor": "#FFFFFF",
                            "filter": {"value": None, "opacity": 100}, "badges": []},
               "sysinfoDisplay": ["", "", "", "", "", ""], "timeZone": "Asia/Shanghai"}},
    "spec": {"cpu": "AMD Ryzen 7 9700X", "gpu": "NVIDIA GeForce RTX 5090"}}

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    devs = find_devices()
    for d in devs:
        print('HID vid=%04x pid=%04x usage_page=0x%04x usage=0x%04x out_len=%d path=%s'
              % (d['vid'], d['pid'], d['usage_page'], d['usage'], d['out_len'], d['path']))
    dev = pick_target(devs)
    print('selected:', hex(dev['vid']), hex(dev['pid']), 'out_len', dev['out_len'])
    if mode == 'probe':
        return
    if mode == 'conn':
        send_post(dev, 'conn', [], b'')
        return
    if mode == 'config-url':
        url = sys.argv[2]
        j = json.loads(json.dumps(DEFAULT_JSON))
        j['waterBlockScreen']['id']['media'] = [url]
        body = json.dumps(j, separators=(',', ':'), ensure_ascii=False).encode()
        send_post(dev, 'config', [], body)
        return
    if mode == 'config':
        body = open(sys.argv[2], 'rb').read()
        send_post(dev, 'config', [], body)
        return
    raise SystemExit('unknown mode ' + mode)

if __name__ == '__main__':
    main()



