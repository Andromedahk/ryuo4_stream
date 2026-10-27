import zipfile
z=zipfile.ZipFile(r"D:\ROG longwang4\firmware-build\extracted_apk.bin")
for i in z.infolist():
    print(i.filename, 'method',i.compress_type,'csize',i.compress_size,'size',i.file_size,'offset',i.header_offset)
