using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
class PortableKobold {
 static int Main(string[] args) {
  string root=AppDomain.CurrentDomain.BaseDirectory;
  try {
   string full=Path.Combine(root,"KoboldCpp.exe");
   if(File.Exists(full)){Process.Start(new ProcessStartInfo(full){WorkingDirectory=root,UseShellExecute=false});return 0;}
   string python=Path.Combine(root,"runtime","python","pythonw.exe"), script=Path.Combine(root,"tools","AutoStart.py"), native=Path.Combine(root,"koboldcpp-nocuda.exe");
   if(!File.Exists(python)||!File.Exists(script)||!File.Exists(native))throw new IOException("Run Setup first or copy the complete portable kit.");
   var start=new ProcessStartInfo(python,"-I -B \""+script+"\""){WorkingDirectory=root,UseShellExecute=false,CreateNoWindow=true};Process.Start(start);
   Process.Start(new ProcessStartInfo(native,"--media-settings"){WorkingDirectory=root,UseShellExecute=false});return 0;
  } catch(Exception error){MessageBox.Show(error.Message,"KoboldCpp",MessageBoxButtons.OK,MessageBoxIcon.Error);return 2;}
 }
}
