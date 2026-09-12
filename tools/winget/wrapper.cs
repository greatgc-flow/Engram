using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace Engram {
    static class Program {
        [DllImport("kernel32.dll", EntryPoint = "CreateFileW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafeFileHandle CreateFile(
            string lpFileName,
            uint dwDesiredAccess,
            uint dwShareMode,
            IntPtr lpSecurityAttributes,
            uint dwCreationDisposition,
            uint dwFlagsAndAttributes,
            IntPtr hTemplateFile
        );

        [DllImport("kernel32.dll", EntryPoint = "GetFinalPathNameByHandleW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetFinalPathNameByHandle(
            SafeFileHandle hFile,
            [Out] StringBuilder lpszFilePath,
            uint cchFilePath,
            uint dwFlags
        );

        private static string GetFinalPath(string path) {
            try {
                // dwDesiredAccess = 0 (file query), dwShareMode = 7 (read/write/delete),
                // dwCreationDisposition = 3 (OPEN_EXISTING), flags = 0x02000000 (FILE_FLAG_BACKUP_SEMANTICS)
                using (SafeFileHandle handle = CreateFile(path, 0, 7, IntPtr.Zero, 3, 0x02000000, IntPtr.Zero)) {
                    if (handle.IsInvalid) {
                        return Path.GetFullPath(path);
                    }
                    StringBuilder sb = new StringBuilder(1024);
                    uint res = GetFinalPathNameByHandle(handle, sb, (uint)sb.Capacity, 0);
                    if (res == 0) {
                        return Path.GetFullPath(path);
                    }
                    string resolved = sb.ToString();
                    if (resolved.StartsWith(@"\\?\UNC\")) {
                        return @"\\" + resolved.Substring(8);
                    }
                    if (resolved.StartsWith(@"\\?\")) {
                        return resolved.Substring(4);
                    }
                    return resolved;
                }
            } catch {
                return Path.GetFullPath(path);
            }
        }

        private static string EscapeArg(string arg) {
            if (string.IsNullOrEmpty(arg)) {
                return "\"\"";
            }
            bool needsQuotes = false;
            for (int i = 0; i < arg.Length; i++) {
                char c = arg[i];
                if (char.IsWhiteSpace(c) || c == '\"' || c == '&' || c == '^' || c == '!' || c == '|' || c == '<' || c == '>' || c == '%') {
                    needsQuotes = true;
                    break;
                }
            }
            if (!needsQuotes) {
                return arg;
            }

            StringBuilder sb = new StringBuilder();
            sb.Append('\"');
            int backslashes = 0;
            for (int i = 0; i < arg.Length; i++) {
                char c = arg[i];
                if (c == '\\') {
                    backslashes++;
                } else if (c == '\"') {
                    sb.Append(new string('\\', backslashes * 2 + 1));
                    sb.Append('\"');
                    backslashes = 0;
                } else {
                    if (backslashes > 0) {
                        sb.Append(new string('\\', backslashes));
                        backslashes = 0;
                    }
                    sb.Append(c);
                }
            }
            if (backslashes > 0) {
                sb.Append(new string('\\', backslashes * 2));
            }
            sb.Append('\"');
            return sb.ToString();
        }

        static int Main(string[] args) {
            string rawExePath = Process.GetCurrentProcess().MainModule.FileName;
            string exePath = GetFinalPath(rawExePath);
            string exeDir = Path.GetDirectoryName(exePath);
            string engramCmd = Path.Combine(exeDir, "engram.cmd");

            if (!File.Exists(engramCmd)) {
                Console.Error.WriteLine("engram.cmd not found next to " + exePath);
                return 1;
            }

            // v3.2.7-only special case: with no args AND _sys\env\python\python.exe absent, forward "install"
            string pythonExe = Path.Combine(exeDir, "_sys", "env", "python", "python.exe");
            if (args.Length == 0 && !File.Exists(pythonExe)) {
                args = new string[] { "install" };
            }

            StringBuilder cmdLine = new StringBuilder();
            cmdLine.Append("/d /s /c \"\"");
            cmdLine.Append(engramCmd);
            cmdLine.Append('\"');

            foreach (string arg in args) {
                cmdLine.Append(' ');
                cmdLine.Append(EscapeArg(arg));
            }
            cmdLine.Append('\"');

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "cmd.exe";
            psi.Arguments = cmdLine.ToString();
            psi.UseShellExecute = false;

            try {
                using (Process child = Process.Start(psi)) {
                    child.WaitForExit();
                    return child.ExitCode;
                }
            } catch (Exception ex) {
                Console.Error.WriteLine("[Error] Failed to launch engram.cmd: " + ex.Message);
                return 1;
            }
        }
    }
}
