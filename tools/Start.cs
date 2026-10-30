using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
class PortableKobold {
 static int Main(string[] args) {
  string root=AppDomain.CurrentDomain.BaseDirectory;
  try {
   string full=Path.Combine(root,"KoboldCpp.exe");
   if(!File.Exists(full))throw new IOException("KoboldCpp.exe is missing. Build or install the complete universal media package first.");
   Process.Start(new ProcessStartInfo(full){WorkingDirectory=root,UseShellExecute=false});return 0;
  } catch(Exception error){MessageBox.Show(error.Message,"KoboldCpp",MessageBoxButtons.OK,MessageBoxIcon.Error);return 2;}
 }
}
