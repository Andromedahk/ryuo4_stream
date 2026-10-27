// ============================================================================
//  Hid.cs - host-side driver for the ROG RYUO IV 1024-byte HID protocol
//
//  Reverse engineered from the device-side SerialService logs (hidserver_log.txt)
//  and the ASUS Info Hub main process:
//    frame  = 0x5A | total_len(2, big endian) | ASCII payload | checksum | 0x5A
//    total_len = len(ASCII) + 5
//    checksum  = (sum(total_len bytes) + sum(ASCII payload)) & 0xFF
//    ASCII payload = "POST <cmd> <ver>\r\n" + "Key=Value\r\n"* + "\r\n" + body
//  Transport: HID OUT report, report id 0, 1024-byte payload (Windows HID
//  OutputReportByteLength = 1025 -> leading 0x00 report id).
//
//  Known quirk: a raw 0x5A byte inside the payload corrupts the device framing.
//  Config JSON therefore escapes 'Z' as \u005A (JSON-equivalent, no 0x5A byte).
// ============================================================================

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace RyuoStreamTest
{
    internal static class HidFrame
    {
        public static byte[] Build(string cmd, string version, List<KeyValuePair<string, string>> headers, byte[] body)
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("POST ").Append(cmd).Append(' ').Append(version).Append("\r\n");
            foreach (KeyValuePair<string, string> kv in headers)
                sb.Append(kv.Key).Append('=').Append(kv.Value).Append("\r\n");
            sb.Append("\r\n");
            byte[] head = Encoding.ASCII.GetBytes(sb.ToString());
            byte[] payload = new byte[head.Length + (body == null ? 0 : body.Length)];
            Buffer.BlockCopy(head, 0, payload, 0, head.Length);
            if (body != null && body.Length > 0) Buffer.BlockCopy(body, 0, payload, head.Length, body.Length);

            int total = payload.Length + 5;
            byte[] frame = new byte[total];
            frame[0] = 0x5A;
            frame[1] = (byte)((total >> 8) & 0xFF);
            frame[2] = (byte)(total & 0xFF);
            Buffer.BlockCopy(payload, 0, frame, 3, payload.Length);
            int sum = 0;
            for (int i = 1; i < 3 + payload.Length; i++) sum += frame[i];
            frame[total - 2] = (byte)(sum & 0xFF);
            frame[total - 1] = 0x5A;
            return frame;
        }

        // Escape 0x5A bytes inside a JSON body as \u005A so the wire frame has no
        // embedded 0x5A delimiter. JSON parsers decode it back to 'Z'.
        public static byte[] EscapeMagic(byte[] json)
        {
            List<byte> outb = new List<byte>(json.Length + 16);
            foreach (byte b in json)
            {
                if (b == 0x5A)
                {
                    foreach (char c in "\\u005A") outb.Add((byte)c);
                }
                else outb.Add(b);
            }
            return outb.ToArray();
        }

        public static bool HasMagic(byte[] data)
        {
            foreach (byte b in data) if (b == 0x5A) return true;
            return false;
        }
    }

    internal sealed class HidDevice : IDisposable
    {
        // ---- win32 interop ----
        [StructLayout(LayoutKind.Sequential)]
        private struct GUID { public uint Data1; public ushort Data2; public ushort Data3; [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)] public byte[] Data4; }

        [StructLayout(LayoutKind.Sequential)]
        private struct SP_DEVICE_INTERFACE_DATA { public uint cbSize; public GUID InterfaceClassGuid; public uint Flags; public IntPtr Reserved; }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct SP_DEVICE_INTERFACE_DETAIL_DATA { public uint cbSize; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 1024)] public string DevicePath; }

        [StructLayout(LayoutKind.Sequential)]
        private struct HIDD_ATTRIBUTES { public uint Size; public ushort VendorID; public ushort ProductID; public ushort VersionNumber; }

        [StructLayout(LayoutKind.Sequential)]
        private struct HIDP_CAPS
        {
            public ushort Usage; public ushort UsagePage;
            public ushort InputReportByteLength; public ushort OutputReportByteLength; public ushort FeatureReportByteLength;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)] public ushort[] Reserved;
            public ushort NumberLinkCollectionNodes;
            public ushort NumberInputButtonCaps; public ushort NumberInputValueCaps; public ushort NumberInputDataIndices;
            public ushort NumberOutputButtonCaps; public ushort NumberOutputValueCaps; public ushort NumberOutputDataIndices;
            public ushort NumberFeatureButtonCaps; public ushort NumberFeatureValueCaps; public ushort NumberFeatureDataIndices;
        }

        [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr SetupDiGetClassDevs(ref GUID guid, IntPtr enumerator, IntPtr hwnd, uint flags);
        [DllImport("setupapi.dll", SetLastError = true)]
        private static extern bool SetupDiEnumDeviceInterfaces(IntPtr set, IntPtr devInfo, ref GUID guid, uint index, ref SP_DEVICE_INTERFACE_DATA data);
        [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr set, ref SP_DEVICE_INTERFACE_DATA data, IntPtr detail, uint detailSize, out uint required, IntPtr devInfo);
        [DllImport("setupapi.dll", SetLastError = true)]
        private static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);
        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_GetAttributes(IntPtr h, ref HIDD_ATTRIBUTES attrs);
        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr pp);
        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_FreePreparsedData(IntPtr pp);
        [DllImport("hid.dll", SetLastError = true)]
        private static extern int HidP_GetCaps(IntPtr pp, ref HIDP_CAPS caps);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateFile(string name, uint access, uint share, IntPtr sec, uint disp, uint flags, IntPtr templ);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool WriteFile(IntPtr h, byte[] buf, uint count, out uint written, IntPtr overlapped);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr h);

        private static readonly Guid HidGuid = new Guid("4D1E55B2-F16F-11CF-88CB-001111000030");
        private IntPtr _handle = new IntPtr(-1);
        public int OutputReportLength;
        public string Path;

        public static List<HidDevice> EnumerateTargets()
        {
            List<HidDevice> list = new List<HidDevice>();
            GUID g = new GUID();
            byte[] gb = HidGuid.ToByteArray();
            g.Data1 = BitConverter.ToUInt32(gb, 0);
            g.Data2 = BitConverter.ToUInt16(gb, 4);
            g.Data3 = BitConverter.ToUInt16(gb, 6);
            g.Data4 = new byte[8];
            Array.Copy(gb, 8, g.Data4, 0, 8);

            IntPtr set = SetupDiGetClassDevs(ref g, IntPtr.Zero, IntPtr.Zero, 0x02 | 0x10);
            if (set == new IntPtr(-1)) return list;
            try
            {
                for (uint i = 0; ; i++)
                {
                    SP_DEVICE_INTERFACE_DATA did = new SP_DEVICE_INTERFACE_DATA();
                    did.cbSize = (uint)Marshal.SizeOf(typeof(SP_DEVICE_INTERFACE_DATA));
                    if (!SetupDiEnumDeviceInterfaces(set, IntPtr.Zero, ref g, i, ref did)) break;
                    uint need;
                    SetupDiGetDeviceInterfaceDetail(set, ref did, IntPtr.Zero, 0, out need, IntPtr.Zero);
                    if (need == 0) continue;
                    IntPtr buf = Marshal.AllocHGlobal((int)need);
                    try
                    {
                        // cbSize is 8 on 64-bit (DWORD + pointer alignment), 6 on 32-bit
                        Marshal.WriteInt32(buf, IntPtr.Size == 8 ? 8 : 6);
                        if (!SetupDiGetDeviceInterfaceDetail(set, ref did, buf, need, out need, IntPtr.Zero)) continue;
                        SP_DEVICE_INTERFACE_DETAIL_DATA detail = (SP_DEVICE_INTERFACE_DETAIL_DATA)Marshal.PtrToStructure(buf, typeof(SP_DEVICE_INTERFACE_DETAIL_DATA));
                        string path = detail.DevicePath;
                        IntPtr h = CreateFile(path, 0x80000000 | 0x40000000, 1 | 2, IntPtr.Zero, 3, 0, IntPtr.Zero);
                        if (h == new IntPtr(-1)) continue;
                        HIDD_ATTRIBUTES attrs = new HIDD_ATTRIBUTES();
                        attrs.Size = (uint)Marshal.SizeOf(typeof(HIDD_ATTRIBUTES));
                        HidD_GetAttributes(h, ref attrs);
                        if (attrs.VendorID == 0x0B05 && attrs.ProductID == 0x1C76)
                        {
                            HIDP_CAPS caps = new HIDP_CAPS();
                            caps.Reserved = new ushort[17];
                            IntPtr pp;
                            if (HidD_GetPreparsedData(h, out pp))
                            {
                                HidP_GetCaps(pp, ref caps);
                                HidD_FreePreparsedData(pp);
                            }
                            if (caps.UsagePage == 0xFF00 || caps.OutputReportByteLength > 65)
                            {
                                HidDevice d = new HidDevice();
                                d._handle = h;
                                d.Path = path;
                                d.OutputReportLength = caps.OutputReportByteLength;
                                if (d.OutputReportLength <= 0) d.OutputReportLength = 1025;
                                list.Add(d);
                                continue;
                            }
                        }
                        CloseHandle(h);
                    }
                    finally { Marshal.FreeHGlobal(buf); }
                }
            }
            finally { SetupDiDestroyDeviceInfoList(set); }
            return list;
        }

        public static HidDevice OpenFirst()
        {
            List<HidDevice> l = EnumerateTargets();
            if (l.Count == 0) throw new Exception("RYUO IV HID interface (VID_0B05 PID_1C76 usage 0xFF00) not found.");
            HidDevice keep = l[0];
            for (int i = 1; i < l.Count; i++) l[i].Dispose();
            return keep;
        }

        public bool Write(byte[] frame)
        {
            int n = OutputReportLength;
            if (frame.Length + 1 > n) throw new Exception("frame too large (" + frame.Length + " > " + (n - 1) + ")");
            byte[] buf = new byte[n];
            buf[0] = 0x00; // report id
            Buffer.BlockCopy(frame, 0, buf, 1, frame.Length);
            uint written;
            bool ok = WriteFile(_handle, buf, (uint)buf.Length, out written, IntPtr.Zero);
            if (!ok)
            {
                int err = Marshal.GetLastWin32Error();
                throw new Exception("HID WriteFile failed, Win32 error " + err);
            }
            return written == buf.Length;
        }

        public void Dispose()
        {
            if (_handle != new IntPtr(-1)) { CloseHandle(_handle); _handle = new IntPtr(-1); }
        }
    }

    internal static class HidProtocol
    {
        private static int _seq = 1000;

        public static void SendConfig(HidDevice dev, string jsonBody)
        {
            byte[] body = Encoding.UTF8.GetBytes(jsonBody);
            body = HidFrame.EscapeMagic(body);
            List<KeyValuePair<string, string>> h = Headers(body.Length);
            byte[] frame = HidFrame.Build("config", "1", h, body);
            Log.Info("HID config frame: " + frame.Length + " bytes, checksum 0x" + frame[frame.Length - 2].ToString("x2"));
            dev.Write(frame);
        }

        public static void SendConn(HidDevice dev)
        {
            byte[] frame = HidFrame.Build("conn", "1", Headers(0), new byte[0]);
            dev.Write(frame);
        }

        public static List<KeyValuePair<string, string>> Headers(int contentLength)
        {
            List<KeyValuePair<string, string>> h = new List<KeyValuePair<string, string>>();
            _seq++;
            h.Add(new KeyValuePair<string, string>("SeqNumber", (Environment.TickCount & 0x7FFFFFFF).ToString()));
            h.Add(new KeyValuePair<string, string>("Date", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString()));
            h.Add(new KeyValuePair<string, string>("ContentType", "json"));
            h.Add(new KeyValuePair<string, string>("ContentLength", contentLength.ToString()));
            return h;
        }

        public static string DefaultConfigJson(string[] media, int brightness)
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{\"temperature\":\"Celsius\",\"waterBlockScreen\":{\"enable\":true,\"displayInSleep\":true,\"brightness\":").Append(brightness).Append(',');
            sb.Append("\"id\":{\"id\":\"Customization\",\"screenMode\":\"Full Screen\",\"playMode\":\"Single\",\"media\":[");
            for (int i = 0; i < media.Length; i++)
            {
                if (i > 0) sb.Append(',');
                sb.Append('"').Append(media[i].Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"');
            }
            sb.Append("],\"settings\":{\"titleColor\":\"#E5252B\",\"contentColor\":\"#FFFFFF\",");
            sb.Append("\"filter\":{\"value\":null,\"opacity\":100},\"badges\":[]},");
            sb.Append("\"sysinfoDisplay\":[\"\",\"\",\"\",\"\",\"\",\"\"],\"timeZone\":\"Asia/Shanghai\"}},");
            sb.Append("\"spec\":{\"cpu\":\"AMD Ryzen 7 9700X\",\"gpu\":\"NVIDIA GeForce RTX 5090\"}}");
            return sb.ToString();
        }
    }
}
