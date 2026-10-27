#!/usr/bin/env python3
"""Rebuild the ROG RYUO IV OTA zip with the modified system image.

Keeps every other entry byte-for-byte (as ZIP_STORED data), preserves entry order
and local header metadata so the `ota-property-files` offsets
(metadata:69:352, metadata.pb:489:232) stay valid.
"""
import os, sys, zipfile, hashlib, struct

BASE = r"D:\ROG longwang4"
SRC_ZIP = os.path.join(BASE, r"firmware\ROG_RYUO_IV_Series_Firmware_File.zip")
OUT_ZIP = os.path.join(BASE, r"firmware-build\ROG_RYUO_IV_Streaming_Firmware_MOD.zip")
USE_ORIG = "--orig" in sys.argv
if USE_ORIG:
    OUT_ZIP = os.path.join(BASE, r"firmware-build\test-repack.zip")
NEW_SYSTEM_BR = os.path.join(BASE, r"firmware-build\system.new.dat.br")
ORIG_SYSTEM_BR = os.path.join(BASE, r"firmware\extracted\system.new.dat.br")

def main():
    use_new = (not USE_ORIG) and os.path.exists(NEW_SYSTEM_BR) and os.path.getsize(NEW_SYSTEM_BR) > 1000000
    src = zipfile.ZipFile(SRC_ZIP, 'r')
    out = zipfile.ZipFile(OUT_ZIP, 'w', allowZip64=True)
    for zi in src.infolist():
        if zi.filename == 'system.new.dat.br' and use_new:
            data = open(NEW_SYSTEM_BR, 'rb').read()
        else:
            data = src.read(zi.filename)
        # preserve metadata of the original entry
        nzi = zipfile.ZipInfo(zi.filename, date_time=zi.date_time)
        nzi.compress_type = zipfile.ZIP_DEFLATED if zi.compress_type == zipfile.ZIP_DEFLATED else zipfile.ZIP_STORED
        nzi.external_attr = zi.external_attr
        nzi.internal_attr = zi.internal_attr
        nzi.create_system = zi.create_system
        nzi.comment = zi.comment
        nzi.extra = zi.extra
        out.writestr(nzi, data)
        print('%-60s %10d' % (zi.filename, len(data)))
    out.close()
    src.close()

    # verify structure and property-file offsets
    z = zipfile.ZipFile(OUT_ZIP)
    names = [i.filename for i in z.infolist()]
    print('\nentries:', len(names))
    ok = True
    # data offset = header_offset + 30 + len(name) + len(extra)
    for nm, want in (('META-INF/com/android/metadata', 69), ('META-INF/com/android/metadata.pb', 489)):
        zi = z.getinfo(nm)
        data_off = zi.header_offset + 30 + len(nm.encode()) + len(zi.extra)
        print('%s: header=%d data_offset=%d (want %d) size=%d' % (nm, zi.header_offset, data_off, want, zi.file_size))
        if data_off != want:
            ok = False
    meta = z.read('META-INF/com/android/metadata').decode()
    print('metadata:\n' + meta)
    print('property offsets match:', ok)
    print('\nOUT:', OUT_ZIP, os.path.getsize(OUT_ZIP), 'bytes sha256',
          hashlib.sha256(open(OUT_ZIP, 'rb').read()).hexdigest())

if __name__ == '__main__':
    main()



