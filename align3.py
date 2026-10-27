import zipfile
for p in [r"D:\ROG longwang4\apk\build\aligned2.apk"]:
    z=zipfile.ZipFile(p)
    for i in z.infolist():
        off=i.header_offset+30+len(i.filename.encode())+len(i.extra)
        print(i.filename,'extra',len(i.extra),'data_off',off,'mod4',off%4,'mod4096',off%4096)
