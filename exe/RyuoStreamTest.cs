// ============================================================================
//  RyuoStreamTest.exe
//  ASUS ROG RYUO IV SLC 360 ARGB AIO cooler-screen USB video-stream tester
//
//  Built from reverse engineering of:
//    * ASUS Info Hub - ROG RYUO IV (Electron app 0.7.7 / main-process V8 bytecode)
//    * on-device Android 13 (Rockchip RK3562, cm16, build V1.0.10) over ADB root
//    * official OTA firmware ROG_RYUO_IV_Series_Firmware_File.zip
//
//  Target USB device (verified): USB\VID_0B05&PID_1C76  "ROG RYUO IV Standard"
//  serial TC26011200324725, composite: MI_00 HID (1024-byte framed protocol),
//  MI_01 ADB (ff/42/01, WinUSB).  Panel: 2240x1080 logical, 60 Hz.
//
//  Stream path proven by this tool:
//    host ffmpeg -> MPEG-TS over HTTP (127.0.0.1:PORT)
//      -> adb reverse tcp:PORT -> on-device StreamActivity (MediaPlayer, hw decode)
//  Fallback path (no app): ffmpeg -> file -> adb push /sdcard/pcMedia (loop playback)
//
//  Build: csc.exe (see build.bat).  .NET Framework 4.x only, no NuGet deps.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace RyuoStreamTest
{
    internal sealed class Options
    {
        public string Command = "help";
        public string Serial = "TC26011200324725";
        public string AdbPath;
        public string FfmpegPath;
        public string ApkPath;
        public int Port = 18080;
        public string Source = "testsrc";
        public string SourceArg;
        public string Codec = "h264";
        public int Width = 1920;
        public int Height = 960;
        public int Fps = 30;
        public int BitrateKbps = 8000;
        public int Gop = 30;
        public string Preset = "ultrafast";
        public string Tune = "zerolatency";
        public int DurationSec = 0;       // 0 = until Ctrl+C
        public int LatencyMs = 0;         // >0 enables visual latency probe
        public string Transport = "ts";   // ts = progressive MPEG-TS, hls = HLS segments
        public int HlsTime = 1;           // HLS target segment duration (s)
        public int HlsListSize = 3;
        public string Encoder;            // libx264 | libx265 | h264_nvenc | hevc_nvenc
        public string ScreenshotDir;
        public bool NoApp;
        public bool KeepReverse;
        public bool Verbose;
        public string OutFile;
        public string MediaName;
        public int Brightness = 85;
        public int SegmentSec = 1;      // segmented mode: seconds per clip
        public int Segments = 20;       // segmented mode: number of clips
        public string ConfigFile;       // raw JSON body for `hid`
        public bool KeepFiles;
    }

    internal static class Log
    {
        public static bool Verbose;
        public static void Info(string s) { Console.WriteLine("[*] " + s); }
        public static void Ok(string s) { Console.ForegroundColor = ConsoleColor.Green; Console.WriteLine("[+] " + s); Console.ResetColor(); }
        public static void Warn(string s) { Console.ForegroundColor = ConsoleColor.Yellow; Console.WriteLine("[!] " + s); Console.ResetColor(); }
        public static void Err(string s) { Console.ForegroundColor = ConsoleColor.Red; Console.WriteLine("[-] " + s); Console.ResetColor(); }
        public static void Dbg(string s) { if (Verbose) { Console.ForegroundColor = ConsoleColor.DarkGray; Console.WriteLine("    " + s); Console.ResetColor(); } }
    }

    internal static class Paths
    {
        public const string InfoHubDir = @"C:\Program Files\ASUS Info Hub - ROG RYUO IV";
        public const string TargetVidPid = "VID_0B05&PID_1C76";

        public static string FindAdb(Options o)
        {
            if (!string.IsNullOrEmpty(o.AdbPath))
            {
                if (File.Exists(o.AdbPath)) return o.AdbPath;
                throw new Exception("--adb not found: " + o.AdbPath);
            }
            string a = Path.Combine(InfoHubDir, @"bin\adb.exe");
            if (File.Exists(a)) return a;
            string[] dirs = Environment.GetEnvironmentVariable("PATH").Split(';');
            foreach (string d in dirs)
            {
                try
                {
                    string c = Path.Combine(d.Trim(), "adb.exe");
                    if (File.Exists(c)) return c;
                }
                catch { }
            }
            throw new Exception("adb.exe not found. Use --adb <path> or install ASUS Info Hub.");
        }

        public static string FindFfmpeg(Options o)
        {
            if (!string.IsNullOrEmpty(o.FfmpegPath))
            {
                if (File.Exists(o.FfmpegPath)) return o.FfmpegPath;
                throw new Exception("--ffmpeg not found: " + o.FfmpegPath);
            }
            string a = Path.Combine(InfoHubDir, @"bin\ffmpeg.exe");
            if (File.Exists(a)) return a;
            string[] dirs = Environment.GetEnvironmentVariable("PATH").Split(';');
            foreach (string d in dirs)
            {
                try
                {
                    string c = Path.Combine(d.Trim(), "ffmpeg.exe");
                    if (File.Exists(c)) return c;
                }
                catch { }
            }
            throw new Exception("ffmpeg.exe not found. Use --ffmpeg <path>.");
        }

        // adb.exe in the Info Hub needs AdbWinApi.dll / AdbWinUsbApi.dll from its parent dir.
        public static void PrepareEnvironment(string adbPath)
        {
            try
            {
                string dir = Path.GetDirectoryName(adbPath);
                string parent = Path.GetDirectoryName(dir);
                string path = Environment.GetEnvironmentVariable("PATH");
                string add = dir + ";" + parent;
                if (path == null) path = add;
                else if (path.IndexOf(parent, StringComparison.OrdinalIgnoreCase) < 0) path = add + ";" + path;
                Environment.SetEnvironmentVariable("PATH", path);
            }
            catch { }
        }
    }

    // ------------------------------------------------------------------ adb --
    internal sealed class Adb
    {
        public string Exe;
        public string Serial;
        public Adb(string exe, string serial) { Exe = exe; Serial = serial; Paths.PrepareEnvironment(exe); }

        private ProcessStartInfo Psi(string args)
        {
            ProcessStartInfo psi = new ProcessStartInfo(Exe, args);
            psi.UseShellExecute = false;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.CreateNoWindow = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;
            return psi;
        }

        public string Shell(string cmd) { return Run("-s " + Serial + " shell " + Quote(cmd)); }

        public string Run(string args)
        {
            Log.Dbg("adb " + args);
            using (Process p = Process.Start(Psi(args)))
            {
                string o = p.StandardOutput.ReadToEnd();
                string e = p.StandardError.ReadToEnd();
                p.WaitForExit();
                return (o ?? "") + (string.IsNullOrEmpty(e) ? "" : "\n" + e);
            }
        }

        public int RunNoCapture(string args, bool quiet)
        {
            Log.Dbg("adb " + args);
            ProcessStartInfo psi = new ProcessStartInfo(Exe, args);
            psi.UseShellExecute = false;
            psi.RedirectStandardOutput = !quiet;
            psi.RedirectStandardError = !quiet;
            psi.CreateNoWindow = true;
            using (Process p = Process.Start(psi))
            {
                if (!quiet) { p.OutputDataReceived += delegate(object s, DataReceivedEventArgs ev) { if (ev.Data != null) Console.WriteLine("    " + ev.Data); }; p.BeginOutputReadLine(); }
                p.WaitForExit();
                return p.ExitCode;
            }
        }

        public string ExecOut(string args, out byte[] bytes)
        {
            ProcessStartInfo psi = Psi(args);
            using (Process p = Process.Start(psi))
            {
                MemoryStream ms = new MemoryStream();
                byte[] buf = new byte[65536];
                Stream s = p.StandardOutput.BaseStream;
                int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0) ms.Write(buf, 0, n);
                string err = p.StandardError.ReadToEnd();
                p.WaitForExit();
                bytes = ms.ToArray();
                return err;
            }
        }

        public static string Quote(string s)
        {
            if (s == null) return "\"\"";
            return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        }

        public List<string> Devices()
        {
            List<string> list = new List<string>();
            string o = Run("devices");
            foreach (string line in o.Split('\n'))
            {
                string t = line.Trim();
                if (t.Length == 0 || t.StartsWith("List of devices")) continue;
                string[] parts = t.Split('\t');
                if (parts.Length >= 2 && parts[1].Trim() == "device") list.Add(parts[0].Trim());
                else if (parts.Length == 1 && t.IndexOf(' ') > 0) { string id = t.Substring(0, t.IndexOf(' ')); if (id.Length > 4) list.Add(id); }
            }
            return list;
        }
    }

    // -------------------------------------------------------------- ffmpeg --
    internal sealed class Ffmpeg
    {
        public string Exe;
        public Process Proc;
        public long Frames;
        public double Fps;
        public double BitrateKbps;
        public long TotalSize;
        public string LastLine;
        private readonly object _lock = new object();
        private Thread _errThread;
        public volatile bool StopRequested;

        public Ffmpeg(string exe) { Exe = exe; }

        public Process Start(string args, bool redirectStdout)
        {
            ProcessStartInfo psi = new ProcessStartInfo(Exe, args);
            psi.UseShellExecute = false;
            psi.RedirectStandardOutput = redirectStdout;
            psi.RedirectStandardError = true;
            psi.CreateNoWindow = true;
            psi.StandardErrorEncoding = Encoding.UTF8;
            Log.Dbg("ffmpeg " + args);
            Proc = Process.Start(psi);
            _errThread = new Thread(ReadErrLoop);
            _errThread.IsBackground = true;
            _errThread.Start();
            return Proc;
        }

        private void ReadErrLoop()
        {
            try
            {
                string line;
                while ((line = Proc.StandardError.ReadLine()) != null)
                {
                    LastLine = line;
                    // -progress emits one key=value per line, e.g. "frame=117", "fps=29.7", "bitrate=3790.1kbits/s"
                    lock (_lock)
                    {
                        Match m = Regex.Match(line, @"^\s*frame=(\d+)");
                        if (m.Success) Frames = long.Parse(m.Groups[1].Value);
                        m = Regex.Match(line, @"^\s*fps=([\d.]+)");
                        if (m.Success) { double v; if (double.TryParse(m.Groups[1].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out v)) Fps = v; }
                        m = Regex.Match(line, @"^\s*bitrate=([\d.]+)\s*kbits/s");
                        if (m.Success) { double v; if (double.TryParse(m.Groups[1].Value, NumberStyles.Float, CultureInfo.InvariantCulture, out v)) BitrateKbps = v; }
                        m = Regex.Match(line, @"^\s*total_size=(\d+)");
                        if (m.Success) TotalSize = long.Parse(m.Groups[1].Value);
                    }
                    if (Log.Verbose && line.Trim().Length > 0 && !line.StartsWith("frame=") && !line.StartsWith("fps=") && !line.StartsWith("bitrate=") && !line.StartsWith("total_size=") && !line.StartsWith("progress=") && !line.StartsWith("out_time") && !line.StartsWith("dup_") && !line.StartsWith("drop_") && !line.StartsWith("speed=") && !line.StartsWith("stream_"))
                        Log.Dbg("ffmpeg: " + line);
                }
            }
            catch { }
        }

        public void Kill()
        {
            try { if (Proc != null && !Proc.HasExited) Proc.Kill(); } catch { }
        }
    }

    // ------------------------------------------------- http mpeg-ts server --
    internal sealed class HttpTsServer
    {
        private readonly TcpListener _listener;
        private readonly Ffmpeg _ff;
        public volatile bool ClientConnected;
        public volatile bool Stop;
        public long BytesSent;
        public int Port { get { return ((IPEndPoint)_listener.LocalEndpoint).Port; } }

        public HttpTsServer(int port, Ffmpeg ff)
        {
            _ff = ff;
            _listener = new TcpListener(IPAddress.Loopback, port);
            _listener.Start();
        }

        public void ServeAsync()
        {
            Thread t = new Thread(ServeLoop);
            t.IsBackground = true;
            t.Start();
        }

        private void ServeLoop()
        {
            while (!Stop)
            {
                TcpClient c = null;
                try
                {
                    c = _listener.AcceptTcpClient();
                    Log.Info("device connected to stream server from " + c.Client.RemoteEndPoint);
                    ClientConnected = true;
                    c.NoDelay = true;
                    using (NetworkStream ns = c.GetStream())
                    {
                        // read request headers (not strictly needed)
                        ns.ReadTimeout = 5000;
                        byte[] req = new byte[4096];
                        try { ns.Read(req, 0, req.Length); } catch { }
                        string hdr = "HTTP/1.1 200 OK\r\n" +
                                     "Content-Type: video/mp2t\r\n" +
                                     "Cache-Control: no-cache, no-store, must-revalidate\r\n" +
                                     "Pragma: no-cache\r\n" +
                                     "Connection: close\r\n" +
                                     "Access-Control-Allow-Origin: *\r\n\r\n";
                        byte[] hb = Encoding.ASCII.GetBytes(hdr);
                        ns.Write(hb, 0, hb.Length);
                        ns.Flush();
                        Stream src = _ff.Proc.StandardOutput.BaseStream;
                        byte[] buf = new byte[65536];
                        int n;
                        while (!Stop && (n = src.Read(buf, 0, buf.Length)) > 0)
                        {
                            ns.Write(buf, 0, n);
                            BytesSent += n;
                        }
                        try { ns.Flush(); } catch { }
                    }
                }
                catch (Exception ex)
                {
                    if (!Stop) Log.Dbg("server: " + ex.Message);
                }
                finally
                {
                    if (c != null) { try { c.Close(); } catch { } }
                    ClientConnected = false;
                }
                if (Stop) break;
                Thread.Sleep(200);
            }
        }

        public void StopServer() { Stop = true; try { _listener.Stop(); } catch { } }
    }

    // --------------------------------------------------------------- probe --
    internal static class Probe
    {
        public static int Run(Options o)
        {
            string adb = Paths.FindAdb(o);
            string ff = Paths.FindFfmpeg(o);
            Adb a = new Adb(adb, o.Serial);
            Log.Info("adb      : " + adb);
            Log.Info("ffmpeg   : " + ff);
            List<string> devs = a.Devices();
            Log.Info("adb devices: " + (devs.Count == 0 ? "(none)" : string.Join(", ", devs.ToArray())));
            bool found = false;
            foreach (string d in devs) if (d == o.Serial) found = true;
            if (!found)
            {
                Log.Err("target serial " + o.Serial + " not found over adb.");
                Log.Info("Connected screens are NOT necessarily the RYUO IV. Check USB device VID_0B05&PID_1C76.");
                return 2;
            }
            Log.Ok("target device present: " + o.Serial);
            string props = a.Shell("getprop ro.product.version; getprop ro.product.model; getprop ro.build.display.id; getprop ro.build.version.release; getprop ro.soc.model; getprop ro.secure; getprop ro.debuggable; id");
            Console.WriteLine();
            Console.WriteLine("---- device identity ----");
            Console.WriteLine(props.Trim());
            Console.WriteLine();
            Console.WriteLine("---- display ----");
            Console.WriteLine(a.Shell("wm size; wm density; cat /sys/class/graphics/fb0/virtual_size; cat /sys/class/graphics/fb0/bits_per_pixel; cat /sys/class/graphics/fb0/stride").Trim());
            Console.WriteLine();
            Console.WriteLine("---- decoders (H.264/H.265) ----");
            string codecs = a.Shell("cat /vendor/etc/media_codecs*.xml 2>/dev/null | grep -iE 'c2\\.(rk|android)\\.(avc|hevc)' | sort -u");
            Console.WriteLine(codecs.Trim());
            Console.WriteLine();
            Console.WriteLine("---- streaming prerequisites ----");
            Console.WriteLine("stream APK installed : " + (a.Shell("pm list packages com.ryuo.stream").Trim().Length > 0 ? "yes" : "no"));
            Console.WriteLine("adb reverse          : " + (a.Run("reverse --list").Trim().Length == 0 ? "(none)" : a.Run("reverse --list").Trim().Replace("\n", ", ")));
            Console.WriteLine();
            Console.WriteLine("Panel is 2240x1080 @60Hz. HW H.264 decoder max 1920x1088; HEVC max 4096x2160.");
            Console.WriteLine("Recommended: --codec h264 --width 1920 --height 960  OR  --codec hevc --width 2240 --height 1080");
            return 0;
        }
    }

    // -------------------------------------------------------------- install --
    internal static class Installer
    {
        public static int Run(Options o)
        {
            string adb = Paths.FindAdb(o);
            Adb a = new Adb(adb, o.Serial);
            string apk = ResolveApk(o);
            if (apk == null) { Log.Err("stream APK not found (use --apk or place ryuo-stream.apk next to the EXE)."); return 3; }
            Log.Info("installing " + apk);
            int rc = a.RunNoCapture("-s " + o.Serial + " install -r -g " + Adb.Quote(apk), false);
            if (rc != 0) { Log.Err("adb install failed with code " + rc); return rc; }
            Log.Ok("stream app installed: com.ryuo.stream");
            return 0;
        }

        public static string ResolveApk(Options o)
        {
            if (!string.IsNullOrEmpty(o.ApkPath)) return File.Exists(o.ApkPath) ? o.ApkPath : null;
            string side = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "ryuo-stream.apk");
            if (File.Exists(side)) return side;
            try
            {
                Assembly asm = Assembly.GetExecutingAssembly();
                Stream s = asm.GetManifestResourceStream("RyuoStream.apk");
                if (s != null)
                {
                    string tmp = Path.Combine(Path.GetTempPath(), "ryuo-stream-" + Guid.NewGuid().ToString("N") + ".apk");
                    using (FileStream fs = File.Create(tmp)) s.CopyTo(fs);
                    Log.Dbg("embedded APK extracted to " + tmp);
                    return tmp;
                }
            }
            catch { }
            return null;
        }
    }

    // ---------------------------------------------- static file http server --
    internal sealed class HttpFileServer
    {
        private readonly TcpListener _listener;
        private readonly string _root;
        private readonly string _mainFile;
        public volatile bool Stop;
        public long BytesSent;
        public int Hits;
        public int Port { get { return ((IPEndPoint)_listener.LocalEndpoint).Port; } }

        public HttpFileServer(int port, string root, string mainFile)
        {
            _root = root; _mainFile = mainFile;
            _listener = new TcpListener(IPAddress.Loopback, port);
            _listener.Start();
        }

        public void ServeAsync()
        {
            Thread t = new Thread(Loop); t.IsBackground = true; t.Start();
        }

        private void Loop()
        {
            while (!Stop)
            {
                TcpClient c = null;
                try
                {
                    c = _listener.AcceptTcpClient();
                    c.NoDelay = true;
                    using (NetworkStream ns = c.GetStream())
                    {
                        ns.ReadTimeout = 3000;
                        byte[] buf = new byte[4096];
                        int n = 0;
                        try { n = ns.Read(buf, 0, buf.Length); } catch { }
                        string req = Encoding.ASCII.GetString(buf, 0, n);
                        string path = "/";
                        string[] lines = req.Split(new string[] { "\r\n" }, StringSplitOptions.None);
                        if (lines.Length > 0)
                        {
                            string[] parts = lines[0].Split(' ');
                            if (parts.Length > 1) path = parts[1];
                        }
                        int q = path.IndexOf('?');
                        if (q >= 0) path = path.Substring(0, q);
                        string name = path.TrimStart('/');
                        if (name.Length == 0) name = _mainFile;
                        string full = Path.Combine(_root, name.Replace('/', '\\'));
                        byte[] body;
                        string mime;
                        if (File.Exists(full))
                        {
                            try { body = File.ReadAllBytes(full); }
                            catch { body = new byte[0]; }
                            mime = name.EndsWith(".m3u8") ? "application/vnd.apple.mpegurl" : "video/mp2t";
                            Hits++;
                        }
                        else
                        {
                            body = Encoding.ASCII.GetBytes("not found");
                            mime = "text/plain";
                        }
                        string hdr = "HTTP/1.1 " + (body.Length > 0 ? "200 OK" : "404 Not Found") + "\r\n" +
                                     "Content-Type: " + mime + "\r\n" +
                                     "Cache-Control: no-cache, no-store, must-revalidate\r\n" +
                                     "Pragma: no-cache\r\n" +
                                     "Connection: close\r\n" +
                                     "Content-Length: " + body.Length + "\r\n\r\n";
                        byte[] hb = Encoding.ASCII.GetBytes(hdr);
                        ns.Write(hb, 0, hb.Length);
                        if (body.Length > 0) { ns.Write(body, 0, body.Length); BytesSent += body.Length; }
                    }
                }
                catch { }
                finally { if (c != null) { try { c.Close(); } catch { } } }
                if (Stop) break;
            }
        }

        public void StopServer() { Stop = true; try { _listener.Stop(); } catch { } }
    }

    // ------------------------------------------------------------ hid/play --
    internal static class HidPlay
    {
        private static string SafeName(string name)
        {
            StringBuilder sb = new StringBuilder();
            foreach (char c in name)
                if (char.IsLetterOrDigit(c) || c == '.' || c == '_' || c == '-') sb.Append(c);
            if (sb.Length == 0) sb.Append("ryuo_media.mp4");
            return sb.ToString();
        }

        public static int Hid(Options o)
        {
            string json = null;
            if (!string.IsNullOrEmpty(o.ConfigFile))
            {
                if (!File.Exists(o.ConfigFile)) { Log.Err("config file not found: " + o.ConfigFile); return 3; }
                json = File.ReadAllText(o.ConfigFile);
            }
            else
            {
                string media = o.MediaName ?? "2026-10-07_11-59-09-827.mp4";
                json = HidProtocol.DefaultConfigJson(new string[] { media }, o.Brightness);
            }
            using (HidDevice dev = HidDevice.OpenFirst())
            {
                Log.Ok("HID target: " + dev.Path);
                HidProtocol.SendConfig(dev, json);
                Log.Ok("config sent (" + json.Length + " chars JSON)");
            }
            return 0;
        }

        private static string EncodeSegment(Options o, string ffmpeg, string outPath, int index)
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("-hide_banner -y -loglevel error ");
            if (o.Source.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
            {
                string f = o.SourceArg ?? o.Source.Substring(5);
                sb.Append("-stream_loop -1 -ss ").Append((index * o.SegmentSec) % 600).Append(" -t ").Append(o.SegmentSec);
                sb.Append(" -i ").Append(Adb.Quote(f)).Append(' ');
                sb.Append("-vf ").Append(Adb.Quote("scale=" + o.Width + ":" + o.Height + ":force_original_aspect_ratio=decrease,pad=" + o.Width + ":" + o.Height + ":(ow-iw)/2:(oh-ih)/2")).Append(' ');
            }
            else if (o.Source.Equals("screen", StringComparison.OrdinalIgnoreCase))
            {
                sb.Append("-f gdigrab -framerate ").Append(o.Fps).Append(" -t ").Append(o.SegmentSec).Append(" -i desktop ");
                sb.Append("-vf ").Append(Adb.Quote("scale=" + o.Width + ":" + o.Height + ":force_original_aspect_ratio=decrease,pad=" + o.Width + ":" + o.Height + ":(ow-iw)/2:(oh-ih)/2")).Append(' ');
            }
            else
            {
                sb.Append("-f lavfi -i ").Append(Adb.Quote("testsrc2=size=" + o.Width + "x" + o.Height + ":rate=" + o.Fps)).Append(' ');
                sb.Append("-t ").Append(o.SegmentSec).Append(' ');
            }
            int gop = o.Gop <= 0 ? o.Fps : o.Gop;
            if (o.Codec.Equals("hevc", StringComparison.OrdinalIgnoreCase) || o.Codec.Equals("h265", StringComparison.OrdinalIgnoreCase))
            {
                sb.Append("-c:v libx265 -preset ").Append(o.Preset).Append(" -pix_fmt yuv420p ");
                sb.Append("-b:v ").Append(o.BitrateKbps).Append("k ");
                sb.Append("-x265-params ").Append(Adb.Quote("keyint=" + gop + ":min-keyint=" + gop + ":scenecut=0")).Append(' ');
            }
            else
            {
                sb.Append("-c:v libx264 -preset ").Append(o.Preset).Append(" -tune zerolatency -profile:v high -pix_fmt yuv420p ");
                sb.Append("-b:v ").Append(o.BitrateKbps).Append("k -maxrate ").Append(o.BitrateKbps).Append("k ");
                sb.Append("-g ").Append(gop).Append(" -keyint_min ").Append(gop).Append(" -sc_threshold 0 ");
                sb.Append("-x264-params ").Append(Adb.Quote("repeat-headers=1:keyint=" + gop + ":min-keyint=" + gop + ":scenecut=0")).Append(' ');
            }
            sb.Append("-an -movflags +faststart ").Append(Adb.Quote(outPath));
            ProcessStartInfo psi = new ProcessStartInfo(ffmpeg, sb.ToString());
            psi.UseShellExecute = false; psi.CreateNoWindow = true; psi.RedirectStandardError = true;
            using (Process p = Process.Start(psi))
            {
                string err = p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (p.ExitCode != 0) throw new Exception("ffmpeg encode failed: " + err.Trim());
            }
            return outPath;
        }

        public static int Play(Options o)
        {
            string adbExe = Paths.FindAdb(o);
            string ffmpeg = Paths.FindFfmpeg(o);
            Adb a = new Adb(adbExe, o.Serial);
            if (!a.Devices().Contains(o.Serial)) { Log.Err("target screen not connected"); return 2; }

            string name = o.MediaName ?? ("ryuo_play_" + DateTime.Now.ToString("HHmmss") + ".mp4");
            name = SafeName(name);
            string tmp = Path.Combine(Path.GetTempPath(), name);
            Log.Info("encoding " + o.Width + "x" + o.Height + " @" + o.Fps + "fps " + o.Codec + " " + o.BitrateKbps + "kbps -> " + name);
            EncodeSegment(o, ffmpeg, tmp, 0);
            Log.Ok("encoded " + new FileInfo(tmp).Length + " bytes");

            DateTime t0 = DateTime.Now;
            int rc = a.RunNoCapture("-s " + o.Serial + " push " + Adb.Quote(tmp) + " /sdcard/pcMedia/" + name, true);
            if (rc != 0) { Log.Err("adb push failed"); return 4; }
            double pushMs = (DateTime.Now - t0).TotalMilliseconds;

            string json = HidProtocol.DefaultConfigJson(new string[] { name }, o.Brightness);
            using (HidDevice dev = HidDevice.OpenFirst())
            {
                HidProtocol.SendConfig(dev, json);
            }
            Log.Ok("HID config sent (media=" + name + ")");
            Log.Info("push took " + pushMs.ToString("F0") + " ms; waiting for player...");
            if (o.ScreenshotDir != null)
            {
                Thread.Sleep(2500);
                if (!Directory.Exists(o.ScreenshotDir)) Directory.CreateDirectory(o.ScreenshotDir);
                byte[] png;
                a.ExecOut("-s " + o.Serial + " exec-out screencap -p", out png);
                string sp = Path.Combine(o.ScreenshotDir, "play_" + DateTime.Now.ToString("HHmmss") + ".png");
                File.WriteAllBytes(sp, png);
                Log.Ok("screenshot: " + sp + " (" + png.Length + " bytes)");
            }
            Log.Ok("playback switched. File kept at /sdcard/pcMedia/" + name + (o.KeepFiles ? "" : " (removed by restore)"));
            return 0;
        }

        // Segmented near-live mode: encode short clips, push, and force HomeUI to
        // switch to each new clip via the HID config channel. Measures how fast
        // content can actually be updated on the panel through the stock player.
        public static int Segmented(Options o)
        {
            string adbExe = Paths.FindAdb(o);
            string ffmpeg = Paths.FindFfmpeg(o);
            Adb a = new Adb(adbExe, o.Serial);
            if (!a.Devices().Contains(o.Serial)) { Log.Err("target screen not connected"); return 2; }

            string baseName = o.MediaName ?? "ryuo_seg";
            baseName = SafeName(baseName).Replace(".mp4", "");
            string jsonTail = null;
            DateTime start = DateTime.Now;
            int done = 0;
            using (HidDevice dev = HidDevice.OpenFirst())
            {
                Log.Ok("HID target: " + dev.Path);
                for (int i = 0; i < o.Segments; i++)
                {
                    string name = baseName + "_" + i + ".mp4";
                    string tmp = Path.Combine(Path.GetTempPath(), name);
                    DateTime tSeg = DateTime.Now;
                    EncodeSegment(o, ffmpeg, tmp, i);
                    double encMs = (DateTime.Now - tSeg).TotalMilliseconds;
                    int rc = a.RunNoCapture("-s " + o.Serial + " push " + Adb.Quote(tmp) + " /sdcard/pcMedia/" + name, true);
                    if (rc != 0) { Log.Err("push failed at segment " + i); break; }
                    double pushMs = (DateTime.Now - tSeg).TotalMilliseconds - encMs;
                    jsonTail = HidProtocol.DefaultConfigJson(new string[] { name }, o.Brightness);
                    DateTime tSwitch = DateTime.Now;
                    HidProtocol.SendConfig(dev, jsonTail);
                    double switchMs = (DateTime.Now - tSwitch).TotalMilliseconds;
                    double total = (DateTime.Now - tSeg).TotalMilliseconds;
                    done++;
                    Console.WriteLine(string.Format("  seg {0,3}  encode={1,5:F0}ms push={2,4:F0}ms hid={3,4:F0}ms total={4,5:F0}ms  -> {5:F2} updates/s",
                        i, encMs, pushMs, switchMs, total, 1000.0 / total));
                    if (o.DurationSec > 0 && (DateTime.Now - start).TotalSeconds >= o.DurationSec) break;
                }
            }
            double elapsed = (DateTime.Now - start).TotalSeconds;
            Log.Ok(string.Format("segmented playback: {0} clips in {1:F1}s = {2:F2} updates/s (this is the stock-player limit)", done, elapsed, done / elapsed));
            Log.Info("restore normal screen with: RyuoStreamTest.exe restore");
            return 0;
        }

        public static int RestoreScreen(Options o)
        {
            string adbExe = Paths.FindAdb(o);
            Adb a = new Adb(adbExe, o.Serial);
            if (!a.Devices().Contains(o.Serial)) { Log.Err("target screen not connected"); return 2; }
            // put the original media back through the HID config channel
            string json = HidProtocol.DefaultConfigJson(new string[] { "2026-10-07_11-59-09-827.mp4" }, o.Brightness);
            using (HidDevice dev = HidDevice.OpenFirst()) HidProtocol.SendConfig(dev, json);
            Log.Ok("screen config restored (original media)");
            a.Shell("rm -f /sdcard/pcMedia/ryuo_*.mp4 /sdcard/pcMedia/live.m3u8 /sdcard/pcMedia/seg*.ts /sdcard/pcMedia/live*.mp4 /sdcard/pcMedia/ts_test.mp4");
            Log.Ok("test media files removed from /sdcard/pcMedia");
            return 0;
        }
    }

    // --------------------------------------------------------------- stream --
    internal static class Streamer
    {
        public static int Run(Options o)
        {
            string adb = Paths.FindAdb(o);
            string ffmpeg = Paths.FindFfmpeg(o);
            Adb a = new Adb(adb, o.Serial);

            // -- target verification -----------------------------------------
            List<string> devs = a.Devices();
            if (!devs.Contains(o.Serial))
            {
                Log.Err("Target screen not connected over adb (serial " + o.Serial + "). Aborting to avoid touching other screens.");
                return 2;
            }
            Log.Ok("verified target serial " + o.Serial);

            // -- ensure app --------------------------------------------------
            bool installed = a.Shell("pm list packages com.ryuo.stream").IndexOf("com.ryuo.stream") >= 0;
            if (!installed && !o.NoApp)
            {
                Log.Warn("stream APK not installed; installing...");
                int irc = Installer.Run(o);
                if (irc != 0) return irc;
            }

            // -- ffmpeg ------------------------------------------------------
            bool hls = o.Transport.Equals("hls", StringComparison.OrdinalIgnoreCase);
            string hlsDir = null;
            string playlist = null;
            if (hls)
            {
                hlsDir = Path.Combine(Path.GetTempPath(), "ryuo_hls_" + DateTime.Now.ToString("yyyyMMdd_HHmmss"));
                Directory.CreateDirectory(hlsDir);
                playlist = Path.Combine(hlsDir, "live.m3u8");
            }
            Ffmpeg ff = new Ffmpeg(ffmpeg);
            string ffargs = BuildFfmpegArgs(o, hlsDir);
            Log.Info("encoding: " + o.Width + "x" + o.Height + " @" + o.Fps + "fps " + o.Codec + " " + o.BitrateKbps + "kbps, source=" + o.Source + (o.SourceArg != null ? " (" + o.SourceArg + ")" : ""));
            Log.Info("transport: " + (hls ? "HLS segments (" + o.HlsTime + "s, list " + o.HlsListSize + ")" : "progressive MPEG-TS"));
            Log.Dbg("ffmpeg " + ffargs);

            HttpTsServer tsServer = null;
            HttpFileServer fileServer = null;
            bool reverseAdded = false;
            try
            {
                if (hls)
                {
                    ff.Start(ffargs, false);
                    Thread.Sleep(1200); // let the first segment + playlist appear
                    fileServer = new HttpFileServer(o.Port, hlsDir, "live.m3u8");
                    fileServer.ServeAsync();
                    Log.Ok("HLS over HTTP listening on 127.0.0.1:" + fileServer.Port + "/live.m3u8");
                }
                else
                {
                    ff.Start(ffargs, true);
                    if (ff.Proc == null || ff.Proc.HasExited)
                    {
                        Log.Err("ffmpeg failed to start.");
                        return 4;
                    }
                    tsServer = new HttpTsServer(o.Port, ff);
                    tsServer.ServeAsync();
                    Log.Ok("MPEG-TS over HTTP listening on 127.0.0.1:" + tsServer.Port + "/live.ts");
                }

                // -- adb reverse --------------------------------------------
                a.Run("reverse --remove tcp:" + o.Port);
                string rev = a.Run("reverse tcp:" + o.Port + " tcp:" + o.Port);
                reverseAdded = true;
                Log.Ok("adb reverse tcp:" + o.Port + " -> host " + o.Port + (rev.Trim().Length > 0 ? " (" + rev.Trim() + ")" : ""));

                // -- launch app ---------------------------------------------
                if (!o.NoApp)
                {
                    string url = hls ? "http://127.0.0.1:" + o.Port + "/live.m3u8" : "http://127.0.0.1:" + o.Port + "/live.ts";
                    a.Shell("am force-stop com.ryuo.stream");
                    string start = a.Shell("am start -n com.ryuo.stream/.StreamActivity --es url " + url + " --ez hud true");
                    Log.Info("launching on screen: " + start.Trim());
                    if (start.IndexOf("Error", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        Log.Err("activity launch failed. Is the APK activity name correct?");
                        return 5;
                    }
                }

                // -- run ------------------------------------------------------
                Console.WriteLine();
                Console.WriteLine("Streaming. Press Ctrl+C to stop." + (o.DurationSec > 0 ? " (duration " + o.DurationSec + "s)" : ""));
                DateTime startAt = DateTime.UtcNow;
                long lastBytes = 0;
                int ticks = 0;
                while (true)
                {
                    Thread.Sleep(1000);
                    ticks++;
                    if (o.DurationSec > 0 && (DateTime.UtcNow - startAt).TotalSeconds >= o.DurationSec) break;
                    if (ff.Proc.HasExited) { Log.Warn("ffmpeg exited (code " + ff.Proc.ExitCode + ")"); break; }
                    long sent;
                    int hits;
                    if (hls) { sent = DirSize(hlsDir); hits = fileServer.Hits; }
                    else { sent = tsServer.BytesSent; hits = tsServer.ClientConnected ? 1 : 0; }
                    long delta = sent - lastBytes;
                    lastBytes = sent;
                    double mbps = delta * 8.0 / 1000000.0;
                    Console.Write(string.Format("\r  t={0,4}s  streamed={1,9:N0} B  now={2,6:F2} Mbps  enc_fps={3,5:F1}  enc_bitrate={4,6:F0} kbps  frame={5,7}  req={6}   ",
                        (int)(DateTime.UtcNow - startAt).TotalSeconds, sent, mbps, ff.Fps, ff.BitrateKbps, ff.Frames, hits));
                    if (o.ScreenshotDir != null && ticks % 10 == 0) TakeScreenshot(a, o, (int)(DateTime.UtcNow - startAt).TotalSeconds);
                }
                Console.WriteLine();

                // -- optional screenshots for latency/QA ---------------------
                if (o.ScreenshotDir != null) TakeScreenshot(a, o, -1);
                return 0;
            }
            catch (Exception ex)
            {
                Log.Err(ex.Message);
                return 6;
            }
            finally
            {
                try { if (tsServer != null) tsServer.StopServer(); } catch { }
                try { if (fileServer != null) fileServer.StopServer(); } catch { }
                try { ff.Kill(); } catch { }
                if (!o.NoApp)
                {
                    try { a.Shell("am force-stop com.ryuo.stream"); } catch { }
                }
                if (reverseAdded && !o.KeepReverse)
                {
                    try { a.Run("reverse --remove tcp:" + o.Port); } catch { }
                }
                if (hlsDir != null) { try { Directory.Delete(hlsDir, true); } catch { } }
                Log.Info("stream stopped, reverse removed.");
            }
        }

        private static long DirSize(string dir)
        {
            long n = 0;
            try { foreach (string f in Directory.GetFiles(dir)) { try { n += new FileInfo(f).Length; } catch { } } }
            catch { }
            return n;
        }

        private static void TakeScreenshot(Adb a, Options o, int sec)
        {
            try
            {
                if (!Directory.Exists(o.ScreenshotDir)) Directory.CreateDirectory(o.ScreenshotDir);
                string name = "screen_" + DateTime.Now.ToString("HHmmss") + (sec >= 0 ? "_t" + sec : "") + ".png";
                string path = Path.Combine(o.ScreenshotDir, name);
                byte[] png;
                a.ExecOut("-s " + a.Serial + " exec-out screencap -p", out png);
                File.WriteAllBytes(path, png);
                Log.Info("screenshot: " + path + " (" + png.Length + " B)");
            }
            catch (Exception ex) { Log.Dbg("screenshot failed: " + ex.Message); }
        }

        public static string BuildFfmpegArgs(Options o, string hlsDir)
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("-hide_banner -nostdin -loglevel warning -progress pipe:2 -nostats ");
            // input
            if (o.Source.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
            {
                string f = o.SourceArg ?? o.Source.Substring(5);
                sb.Append("-stream_loop -1 -re -i " + Adb.Quote(f) + " ");
                sb.Append("-vf " + Adb.Quote("scale=" + o.Width + ":" + o.Height + ":force_original_aspect_ratio=decrease,pad=" + o.Width + ":" + o.Height + ":(ow-iw)/2:(oh-ih)/2") + " ");
            }
            else if (o.Source.Equals("screen", StringComparison.OrdinalIgnoreCase))
            {
                sb.Append("-f gdigrab -framerate " + o.Fps + " -i desktop ");
                sb.Append("-vf " + Adb.Quote("scale=" + o.Width + ":" + o.Height + ":force_original_aspect_ratio=decrease,pad=" + o.Width + ":" + o.Height + ":(ow-iw)/2:(oh-ih)/2") + " ");
            }
            else if (o.Source.Equals("smpte", StringComparison.OrdinalIgnoreCase))
            {
                sb.Append("-re -f lavfi -i " + Adb.Quote("smptebars=size=" + o.Width + "x" + o.Height + ":rate=" + o.Fps) + " ");
            }
            else
            {
                sb.Append("-re -f lavfi -i " + Adb.Quote("testsrc2=size=" + o.Width + "x" + o.Height + ":rate=" + o.Fps) + " ");
            }
            // encoder
            int gop = o.Gop <= 0 ? o.Fps : o.Gop;
            bool hevc = o.Codec.Equals("hevc", StringComparison.OrdinalIgnoreCase) || o.Codec.Equals("h265", StringComparison.OrdinalIgnoreCase);
            string enc = o.Encoder;
            if (string.IsNullOrEmpty(enc)) enc = hevc ? "libx265" : "libx264";
            if (enc.IndexOf("nvenc", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                sb.Append("-c:v " + enc + " -preset p1 -tune ull -zerolatency 1 -pix_fmt yuv420p ");
                sb.Append("-b:v " + o.BitrateKbps + "k -maxrate " + o.BitrateKbps + "k -bufsize " + (o.BitrateKbps * 2) + "k ");
                sb.Append("-g " + gop + " -keyint_min " + gop + " ");
            }
            else if (hevc)
            {
                sb.Append("-c:v " + enc + " -preset " + o.Preset + " -tune " + o.Tune + " -pix_fmt yuv420p ");
                sb.Append("-b:v " + o.BitrateKbps + "k -maxrate " + o.BitrateKbps + "k -bufsize " + (o.BitrateKbps * 2) + "k ");
                sb.Append("-x265-params " + Adb.Quote("repeat-headers=1:keyint=" + gop + ":min-keyint=" + gop + ":scenecut=0") + " ");
            }
            else
            {
                sb.Append("-c:v " + enc + " -preset " + o.Preset + " -tune " + o.Tune + " -profile:v high -pix_fmt yuv420p ");
                sb.Append("-b:v " + o.BitrateKbps + "k -maxrate " + o.BitrateKbps + "k -bufsize " + (o.BitrateKbps * 2) + "k ");
                sb.Append("-g " + gop + " -keyint_min " + gop + " -sc_threshold 0 ");
                sb.Append("-x264-params " + Adb.Quote("repeat-headers=1:keyint=" + gop + ":min-keyint=" + gop + ":scenecut=0") + " ");
            }
            if (hlsDir != null)
            {
                sb.Append("-an -f hls -hls_time " + o.HlsTime + " -hls_list_size " + o.HlsListSize +
                          " -hls_flags delete_segments+omit_endlist -hls_segment_type mpegts " +
                          "-hls_segment_filename " + Adb.Quote(Path.Combine(hlsDir, "seg%05d.ts")) + " " +
                          Adb.Quote(Path.Combine(hlsDir, "live.m3u8")));
            }
            else
            {
                sb.Append("-an -f mpegts -mpegts_flags +resend_headers -flush_packets 1 pipe:1");
            }
            return sb.ToString();
        }
    }

    // ---------------------------------------------------------------- file --
    // Proven fallback: encode a video and push it over /sdcard/pcMedia (HomeUI loops it).
    internal static class FileFallback
    {
        public static int Run(Options o)
        {
            string adb = Paths.FindAdb(o);
            string ffmpeg = Paths.FindFfmpeg(o);
            Adb a = new Adb(adb, o.Serial);
            if (!a.Devices().Contains(o.Serial)) { Log.Err("target screen not connected"); return 2; }

            string name = o.MediaName ?? "2026-10-07_11-59-09-827.mp4";
            string tmp = Path.Combine(Path.GetTempPath(), "ryuo_test_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".mp4");
            StringBuilder args = new StringBuilder();
            args.Append("-hide_banner -y -loglevel warning ");
            int secs = o.DurationSec > 0 ? o.DurationSec : 8;
            if (o.Source.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
            {
                string f = o.SourceArg ?? o.Source.Substring(5);
                args.Append("-stream_loop -1 -t " + secs + " -i " + Adb.Quote(f) + " ");
            }
            else
            {
                args.Append("-f lavfi -i " + Adb.Quote("testsrc2=size=" + o.Width + "x" + o.Height + ":rate=" + o.Fps) + " -t " + secs + " ");
            }
            args.Append("-c:v libx264 -preset veryfast -pix_fmt yuv420p -b:v " + o.BitrateKbps + "k -g " + (o.Gop <= 0 ? o.Fps : o.Gop) + " ");
            args.Append("-movflags +faststart " + Adb.Quote(tmp));

            Log.Info("encoding test video -> " + tmp);
            ProcessStartInfo psi = new ProcessStartInfo(ffmpeg, args.ToString());
            psi.UseShellExecute = false; psi.CreateNoWindow = true; psi.RedirectStandardError = true;
            using (Process p = Process.Start(psi))
            {
                string err = p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (p.ExitCode != 0) { Log.Err("ffmpeg failed: " + err); return 4; }
            }
            Log.Ok("encoded " + new FileInfo(tmp).Length + " bytes");
            Log.Info("pushing to /sdcard/pcMedia/" + name + " (HomeUI re-opens it every loop)");
            int rc = a.RunNoCapture("-s " + o.Serial + " push " + Adb.Quote(tmp) + " /sdcard/pcMedia/" + name, false);
            if (rc != 0) { Log.Err("adb push failed"); return 5; }
            Log.Ok("done. The screen swaps to this clip within one playback loop.");
            Log.Info("Original backup on device: /data/local/tmp/orig_playing_backup.mp4 (restore with --command restore).");
            return 0;
        }
    }

    // -------------------------------------------------------------- restore --
    internal static class Restore
    {
        public static int Run(Options o)
        {
            string adb = Paths.FindAdb(o);
            Adb a = new Adb(adb, o.Serial);
            a.Shell("am force-stop com.ryuo.stream");
            a.Run("reverse --remove-all");
            string bak = a.Shell("ls -l /data/local/tmp/orig_playing_backup.mp4");
            if (bak.IndexOf("No such file", StringComparison.OrdinalIgnoreCase) < 0 && bak.IndexOf("orig_playing_backup") >= 0)
            {
                Log.Info("restoring original media file from /data/local/tmp/orig_playing_backup.mp4");
                Log.Info(a.Shell("cp /data/local/tmp/orig_playing_backup.mp4 /sdcard/pcMedia/2026-10-07_11-59-09-827.mp4 && echo restored").Trim());
            }
            else Log.Warn("no original backup found on device (nothing to restore)");
            Log.Ok("cleanup complete (app stopped, adb reverse cleared).");
            return 0;
        }
    }

    // ----------------------------------------------------------------- main --
    internal static class Program
    {
        private static Options Parse(string[] argv)
        {
            Options o = new Options();
            if (argv.Length == 0) return o;
            o.Command = argv[0].TrimStart('-').ToLowerInvariant();
            for (int i = 1; i < argv.Length; i++)
            {
                string k = argv[i];
                string v = null;
                int eq = k.IndexOf('=');
                if (eq > 0) { v = k.Substring(eq + 1); k = k.Substring(0, eq); }
                else if (i + 1 < argv.Length && !argv[i + 1].StartsWith("-")) { v = argv[++i]; }
                switch (k.ToLowerInvariant())
                {
                    case "--serial": o.Serial = v; break;
                    case "--adb": o.AdbPath = v; break;
                    case "--ffmpeg": o.FfmpegPath = v; break;
                    case "--apk": o.ApkPath = v; break;
                    case "--port": o.Port = int.Parse(v); break;
                    case "--source": o.Source = v; break;
                    case "--file": o.Source = "file:" + v; o.SourceArg = v; break;
                    case "--codec": o.Codec = v; break;
                    case "--width": o.Width = int.Parse(v); break;
                    case "--height": o.Height = int.Parse(v); break;
                    case "--fps": o.Fps = int.Parse(v); break;
                    case "--bitrate": o.BitrateKbps = int.Parse(v); break;
                    case "--gop": o.Gop = int.Parse(v); break;
                    case "--preset": o.Preset = v; break;
                    case "--tune": o.Tune = v; break;
                    case "--duration": o.DurationSec = int.Parse(v); break;
                    case "--transport": o.Transport = v; break;
                    case "--encoder": o.Encoder = v; break;
                    case "--hls-time": o.HlsTime = int.Parse(v); break;
                    case "--hls-list": o.HlsListSize = int.Parse(v); break;
                    case "--latency": o.LatencyMs = int.Parse(v); break;
                    case "--screenshots": o.ScreenshotDir = v; break;
                    case "--no-app": o.NoApp = true; break;
                    case "--keep-reverse": o.KeepReverse = true; break;
                    case "--verbose": o.Verbose = true; Log.Verbose = true; break;
                    case "--out": o.OutFile = v; break;
                    case "--media-name": o.MediaName = v; break;
                    case "--brightness": o.Brightness = int.Parse(v); break;
                    case "--segment": o.SegmentSec = int.Parse(v); break;
                    case "--segments": o.Segments = int.Parse(v); break;
                    case "--config": o.ConfigFile = v; break;
                    case "--keep": o.KeepFiles = true; break;
                    default: Log.Warn("unknown option " + k); break;
                }
            }
            return o;
        }

        private static void Help()
        {
            Console.WriteLine(@"RyuoStreamTest.exe - USB video display tester for ASUS ROG RYUO IV SLC 360 ARGB
Target: USB\VID_0B05&PID_1C76  ""ROG RYUO IV Standard""  (serial TC26011200324725)
Panel : 2240x1080 logical @60Hz, native 1080x2240, Android 13 on Rockchip RK3562

USAGE
  RyuoStreamTest.exe probe     [--serial S]      verify target + dump device/panel/codecs
  RyuoStreamTest.exe play      [options]         encode a clip, push it, switch the screen via HID
  RyuoStreamTest.exe stream    [options]         segmented near-live test (repeated play) + rate stats
  RyuoStreamTest.exe hid       [options]         send a waterBlockScreen config over HID
  RyuoStreamTest.exe netstream [options]         MPEG-TS over adb-reverse HTTP (needs stream APK)
  RyuoStreamTest.exe install   [--apk PATH]      install stream APK (fails on locked production ROMs)
  RyuoStreamTest.exe file      [options]         encode + push only (screen swaps on next loop)
  RyuoStreamTest.exe restore                     restore original screen + remove test media
  RyuoStreamTest.exe help

PLAY / STREAM OPTIONS
  --codec h264|hevc        default h264 (HW caps: h264 <=1920x1088, hevc <=4096x2160)
  --width N --height N     default 1920x960  (use 2240x1080 with hevc for the full panel)
  --fps N                  default 30
  --bitrate N              kbps, default 8000
  --gop N                  keyframe interval, default = fps
  --preset NAME            default ultrafast
  --source testsrc|smpte|screen|file:PATH
  --file PATH              use a local video file as source
  --segment N              stream mode: seconds per clip (default 1)
  --segments N             stream mode: number of clips (default 20)
  --duration N             stream mode: stop after N seconds
  --brightness N           screen brightness 0..255 (default 85)
  --media-name NAME        file name to use under /sdcard/pcMedia
  --screenshots DIR        capture a device screenshot after switching
  --keep                   keep pushed test files
  --verbose
EXAMPLES
  RyuoStreamTest.exe probe
  RyuoStreamTest.exe play --source testsrc --codec h264 --width 1920 --height 960 --fps 30 --bitrate 8000 --screenshots shots
  RyuoStreamTest.exe play --file ""D:\movie.mp4"" --codec hevc --width 2240 --height 1080 --bitrate 12000
  RyuoStreamTest.exe stream --source testsrc --segment 1 --segments 30 --bitrate 6000
  RyuoStreamTest.exe hid --media-name 2026-10-07_11-59-09-827.mp4 --brightness 60
  RyuoStreamTest.exe restore
");
        }

        private static int Main(string[] argv)
        {
            Console.OutputEncoding = Encoding.UTF8;
            try
            {
                Options o = Parse(argv);
                switch (o.Command)
                {
                    case "probe": return Probe.Run(o);
                    case "install": return Installer.Run(o);
                    case "hid": return HidPlay.Hid(o);
                    case "play": return HidPlay.Play(o);
                    case "stream": return HidPlay.Segmented(o);
                    case "netstream": return Streamer.Run(o);
                    case "file": return FileFallback.Run(o);
                    case "restore":
                        {
                            int rc = HidPlay.RestoreScreen(o);
                            int rc2 = Restore.Run(o);
                            return rc != 0 ? rc : rc2;
                        }
                    case "help":
                    case "--help":
                    case "-h": Help(); return 0;
                    default: Help(); return 1;
                }
            }
            catch (Exception ex)
            {
                Log.Err(ex.Message);
                if (Log.Verbose) Console.WriteLine(ex.StackTrace);
                return 7;
            }
        }
    }
}
