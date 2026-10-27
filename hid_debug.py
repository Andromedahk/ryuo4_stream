import ctypes, ctypes.wintypes as wt
setupapi=ctypes.WinDLL('setupapi',use_last_error=True)
GUID=(ctypes.c_ubyte*16)(0x4D,0x1E,0x55,0xB2,0xF1,0x6F,0x11,0xCF,0x88,0xCB,0x00,0x11,0x11,0x00,0x00,0x30)
setupapi.SetupDiGetClassDevsW.argtypes=[ctypes.c_void_p,wt.LPCWSTR,wt.HWND,wt.DWORD]
setupapi.SetupDiGetClassDevsW.restype=wt.HANDLE
setupapi.SetupDiEnumDeviceInterfaces.argtypes=[wt.HANDLE,ctypes.c_void_p,ctypes.c_void_p,wt.DWORD,ctypes.c_void_p]
setupapi.SetupDiEnumDeviceInterfaces.restype=wt.BOOL
h=setupapi.SetupDiGetClassDevsW(ctypes.byref(GUID),None,None,0x12)
print('handle',h,'err',ctypes.get_last_error())
class DID(ctypes.Structure):
    _fields_=[('cbSize',wt.DWORD),('g',ctypes.c_ubyte*16),('flags',wt.DWORD),('res',ctypes.c_void_p)]
d=DID(); d.cbSize=ctypes.sizeof(d)
r=setupapi.SetupDiEnumDeviceInterfaces(h,None,ctypes.byref(GUID),0,ctypes.byref(d))
print('enum0',r,'err',ctypes.get_last_error())
# try 0x02 only
h2=setupapi.SetupDiGetClassDevsW(ctypes.byref(GUID),None,None,0x02)
d2=DID(); d2.cbSize=ctypes.sizeof(d2)
r2=setupapi.SetupDiEnumDeviceInterfaces(h2,None,ctypes.byref(GUID),0,ctypes.byref(d2))
print('enum0 present-only',r2,'err',ctypes.get_last_error())
