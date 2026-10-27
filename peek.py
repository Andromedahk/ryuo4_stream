import struct
src = r"C:\Program Files\ASUS Info Hub - ROG RYUO IV\resources\app.asar"
with open(src,'rb') as f:
    d = f.read(256)
print("len file:", len(open(src,'rb').read(1)))
print("first 64:", d[:64].hex())
print("u32 at 0,4,8,12:", struct.unpack('<IIII', d[0:16]))
print("ascii:", d[:200])
