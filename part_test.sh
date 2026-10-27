for p in /product /system_ext /vendor /odm; do
  echo "=== $p"
  mount -o remount,rw $p
  df -k $p | tail -1
  dd if=/dev/zero of=$p/.__t2 bs=4096 count=8 2>&1 | tail -1
  ls -l $p/.__t2 2>&1
  rm -f $p/.__t2
done