using System;
using System.Diagnostics;
using System.IO;
class PortableKobold {
 static int Main(string[] args) {
  string root=AppDomain.CurrentDomain.BaseDirectory;
  string python=Path.Combine(root,"runtime","python","python.exe");
  string launch=Path.Combine(root,"tools","Launch.py");
  Console.Title="KoboldCpp - portable photo pipeline";
  if(!File.Exists(python)||!File.Exists(launch)){Console.Error.WriteLine("Portable runtime missing. Copy the complete folder.");return 2;}
  string command="-I -B -u \""+launch+"\"";
  foreach(string arg in args){command+=" \""+arg.Replace("\"","\\\"")+"\"";}
  try {
   var start=new ProcessStartInfo(python,command);start.WorkingDirectory=root;start.UseShellExecute=false;start.CreateNoWindow=false;
   using(var process=Process.Start(start)){process.WaitForExit();return process.ExitCode;}
  } catch(Exception error){Console.Error.WriteLine(error.Message);return 3;}
 }
}
