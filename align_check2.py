import zipfile
for p in [r"D:\ROG longwang4\apk\build\base.apk", r"D:\ROG longwang4\apk\build\aligned.apk"]:
    print('==',p)
    z=zipfile.ZipFile(p)
    for i in z.infolist():
        off=i.header_offset+30+len(i.filename.encode())+len(i.extra)
        print(' ',i.filename,'method',i.compress_type,'data_off',off,'mod4',off%4)
