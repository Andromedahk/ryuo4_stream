import zipfile
z=zipfile.ZipFile(r"D:\ROG longwang4\apk\build\base.apk")
for i in z.infolist(): print(i.filename,i.compress_type,i.file_size)
print('---aligned---')
z=zipfile.ZipFile(r"D:\ROG longwang4\apk\build\aligned.apk")
for i in z.infolist(): print(i.filename,i.compress_type,i.file_size)
