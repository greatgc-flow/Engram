using System;
using System.Diagnostics;
using System.IO;

namespace Engram {
    class Program {
        static void Main(string[] args) {
            string currentDir = AppDomain.CurrentDomain.BaseDirectory;
            string installScript = Path.Combine(currentDir, "INSTALL.bat");
            
            if (File.Exists(installScript)) {
                Process p = new Process();
                p.StartInfo.FileName = "cmd.exe";
                p.StartInfo.Arguments = "/c \"" + installScript + "\"";
                p.StartInfo.UseShellExecute = false;
                p.Start();
                p.WaitForExit();
            } else {
                Console.WriteLine("INSTALL.bat not found in " + currentDir);
            }
        }
    }
}
