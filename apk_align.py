import zipfile
p=r"D:\ROG longwang4\apk\ryuo-stream-v2.apk"
z=zipfile.ZipFile(p)
for i in z.infolist():
    print(i.filename,'method',i.compress_type,'off',i.header_offset,'size',i.file_size,'extra',len(i.extra))
# alignment: data offset = header+30+len(name)+len(extra)
for i in z.infolist():
    off=i.header_offset+30+len(i.filename.encode())+len(i.extra)
    print('data_off',i.filename,off,'mod4',off%4)
