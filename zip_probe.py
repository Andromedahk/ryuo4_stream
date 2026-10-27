import zipfile
z=zipfile.ZipFile(r"D:\ROG longwang4\firmware\ROG_RYUO_IV_Series_Firmware_File.zip")
print('entries',len(z.infolist()))
for i in z.infolist()[:12]:
    data_off=i.header_offset+30+len(i.filename.encode())+len(i.extra)
    print('%-55s off=%d data=%d csize=%d size=%d method=%d extra=%d flags=0x%x' % (i.filename,i.header_offset,data_off,i.compress_size,i.file_size,i.compress_type,len(i.extra),i.flag_bits))
print('total zip size', __import__('os').path.getsize(r"D:\ROG longwang4\firmware\ROG_RYUO_IV_Series_Firmware_File.zip"))
print('free D:', __import__('shutil').disk_usage('D:').free)
