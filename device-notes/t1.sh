#!/system/bin/sh
echo "=== pm list packages -f (baiyi/factory/player-like) ==="
pm list packages -f | grep -iE "baiyi|player|video|media|gallery|photo" 
echo "=== which nc curl toybox wget ==="
which nc; which curl; which toybox; which wget; which ffmpeg
echo "=== verifier settings ==="
settings get global verifier_verify_adb_installs
settings get global package_verifier_enable
echo "=== am start VIEW file.mp4 ==="
am start -a android.intent.action.VIEW -d file:///sdcard/pcMedia/2026-10-07_11-59-09-827.mp4 -t video/mp4 2>&1
echo "=== am start VIEW http url ==="
am start -a android.intent.action.VIEW -d http://127.0.0.1:18080/test.mp4 -t video/mp4 2>&1
echo "=== pkgs handling video/mp4 ==="
cmd package query-activities -a android.intent.action.VIEW -t video/mp4 2>&1 | head -30
echo "=== media_codecs files ==="
ls -la /vendor/etc/media_codecs*.xml /vendor/etc/media_codecs*.xml 2>/dev/null
echo "=== codec names ==="
grep -hoE "c2\.(rk\.|android\.)[A-Za-z0-9._-]+" /vendor/etc/media_codecs*.xml 2>/dev/null | sort -u | head -40
echo "=== h264/h265 decoder entries ==="
grep -A6 -iE "avc|hevc" /vendor/etc/media_codecs*.xml 2>/dev/null | grep -iE "name=|max|size|fps|bitrate" | head -30