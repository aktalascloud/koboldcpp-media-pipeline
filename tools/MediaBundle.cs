// Portable single-file media entry. Models are external; code/runtime are embedded.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
class KoboldMediaBundle {
 static readonly string Root=AppDomain.CurrentDomain.BaseDirectory;
 static int Port=5001; static int UiPort=5003;
 static string Read(string name){using(var s=Assembly.GetExecutingAssembly().GetManifestResourceStream(name))using(var r=new StreamReader(s,Encoding.UTF8))return r.ReadToEnd();}
 static string Hash(string text){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-","").ToLowerInvariant();}
 static string Digest(string path){using(var h=SHA256.Create())using(var f=File.OpenRead(path))return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
 static string Safe(string relative){
  if(Path.IsPathRooted(relative)||relative.Contains(":"))throw new IOException("Invalid bundle path");
  string path=Path.GetFullPath(Path.Combine(Root,relative.Replace('/',Path.DirectorySeparatorChar)));
  if(!path.StartsWith(Path.GetFullPath(Root).TrimEnd('\\')+"\\",StringComparison.OrdinalIgnoreCase))throw new IOException("Bundle path leaves application folder");
  for(string d=Path.GetDirectoryName(path);d!=null&&d.Length>=Root.TrimEnd('\\').Length;d=Path.GetDirectoryName(d))
   if(Directory.Exists(d)&&(File.GetAttributes(d)&FileAttributes.ReparsePoint)!=0)throw new IOException("Reparse directory preserved: "+d);
  if(File.Exists(path)&&(File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new IOException("Reparse file preserved");
  return path;
 }
 static void Extract(){
  var js=new JavaScriptSerializer();js.MaxJsonLength=32*1024*1024;
  var manifest=js.Deserialize<Dictionary<string,object>>(Read("media-manifest.json"));
  var rows=(Dictionary<string,object>)manifest["files"];
  using(var resource=Assembly.GetExecutingAssembly().GetManifestResourceStream("media-payload.zip"))
  using(var archive=new ZipArchive(resource,ZipArchiveMode.Read)){
   if(archive.Entries.Count!=rows.Count)throw new IOException("Bundle entry count mismatch");
   var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   foreach(var item in archive.Entries){
    if(!names.Add(item.FullName)||!rows.ContainsKey(item.FullName))throw new IOException("Duplicate/unlisted bundle entry");
    var row=(Dictionary<string,object>)rows[item.FullName];string path=Safe(item.FullName);
    // Existing user configuration/code wins. Scheduled deployment owns upgrades;
    // this executable must never silently roll an installed release backwards.
    if(File.Exists(path))continue;
    Directory.CreateDirectory(Path.GetDirectoryName(path));string temp=path+".unpack-"+Guid.NewGuid().ToString("N");
    try{
     using(var input=item.Open())using(var output=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None))input.CopyTo(output);
     if(new FileInfo(temp).Length!=Convert.ToInt64(row["bytes"])||Digest(temp)!=(string)row["sha256"])throw new IOException("Bundle SHA256 mismatch: "+item.FullName);
     if(!File.Exists(path))File.Move(temp,path);
    }finally{if(File.Exists(temp))File.Delete(temp);}
   }
  }
 }
 static string Get(string path){var req=(HttpWebRequest)WebRequest.Create("http://127.0.0.1:"+Port+path);req.Timeout=3000;using(var r=req.GetResponse())using(var s=new StreamReader(r.GetResponseStream()))return s.ReadToEnd();}
 static int Main(string[] args){
  bool background=Array.IndexOf(args,"--background")>=0;bool native=Array.IndexOf(args,"--native-gui")>=0;
  bool extractOnly=Array.IndexOf(args,"--extract-only")>=0;
  try{
   using(var mutex=new Mutex(false,"Local\\KoboldMediaBundle-"+Hash(Path.GetFullPath(Root)).Substring(0,20))){
    try{if(!mutex.WaitOne(180000))throw new IOException("Another bundle extraction did not finish in time");}
    catch(AbandonedMutexException){} // The new process owns the abandoned mutex.
    try{Extract();}finally{mutex.ReleaseMutex();}
   }
   if(extractOnly)return 0;
   var parser=new JavaScriptSerializer();parser.MaxJsonLength=4*1024*1024;
   var helper=parser.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(Root,"Helper.kcpps")));
   var defaults=helper["gendefaults"] is string?parser.Deserialize<Dictionary<string,object>>((string)helper["gendefaults"]):(Dictionary<string,object>)helper["gendefaults"];
   var proxy=(Dictionary<string,object>)defaults["kcpp_proxy"];Port=Convert.ToInt32(proxy["port"]);UiPort=Port;
   if(proxy.ContainsKey("api_alias_ports")){foreach(object alias in (System.Collections.IEnumerable)proxy["api_alias_ports"]){UiPort=Convert.ToInt32(alias);break;}}
   if(native){Process.Start(new ProcessStartInfo(Path.Combine(Root,"koboldcpp-nocuda.exe"),"--media-settings"){WorkingDirectory=Root,UseShellExecute=false});return 0;}
   if(!background)Process.Start(new ProcessStartInfo(Path.Combine(Root,"koboldcpp-nocuda.exe"),"--media-settings"){WorkingDirectory=Root,UseShellExecute=false});
   var js=new JavaScriptSerializer();js.MaxJsonLength=4*1024*1024;
   bool running=false;
   try{var health=js.Deserialize<Dictionary<string,object>>(Get("/health"));
    if((string)health["service"]!="KoboldProxy"||!String.Equals(Path.GetFullPath((string)health["helper"]),Path.Combine(Root,"Helper.kcpps"),StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("The API port belongs to another installation; preserved");
    running=true;
   }catch(WebException error){if(error.Response!=null)throw;}
   if(!running){var launch=new ProcessStartInfo(Path.Combine(Root,"runtime/python/pythonw.exe"),"-I -B \""+Path.Combine(Root,"tools/AutoStart.py")+"\"");launch.WorkingDirectory=Root;launch.UseShellExecute=false;launch.CreateNoWindow=true;Process.Start(launch);}
   var deadline=DateTime.UtcNow.AddSeconds(180);bool ready=false;
   while(DateTime.UtcNow<deadline){try{var c=js.Deserialize<Dictionary<string,object>>(Get("/v1/media/capabilities"));if((string)c["backend"]=="KoboldCpp"){ready=true;break;}}catch(WebException){}Thread.Sleep(500);}
   if(!ready)throw new IOException("Media startup timed out. Check logs/autostart.log; main models must be present in MODELS, DETAILERS and UPSCALERS.");
   return 0;
  }catch(Exception error){
   try{Directory.CreateDirectory(Path.Combine(Root,"logs"));File.WriteAllText(Path.Combine(Root,"logs/bundle-startup-error.log"),DateTime.Now.ToString("o")+"\n"+error.ToString());}catch{}
   if(!background)MessageBox.Show(error.Message,"KoboldCpp Media",MessageBoxButtons.OK,MessageBoxIcon.Error);
   return 1;
  }
 }
}
