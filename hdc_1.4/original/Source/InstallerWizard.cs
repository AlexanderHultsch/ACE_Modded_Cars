using System;
using System.IO;
using System.IO.Compression;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using System.Reflection;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.Win32;

[assembly: AssemblyTitle("HDC 1.4 Installer")]
[assembly: AssemblyDescription("Hina's Drift Club - The Yard and 6 cars installer")]
[assembly: AssemblyCompany("Hina")]
[assembly: AssemblyProduct("HDC 1.4")]
[assembly: AssemblyCopyright("Hina - Hina's Drift Club")]
[assembly: AssemblyVersion("1.4.0.0")]
[assembly: AssemblyFileVersion("1.4.0.0")]
[assembly: AssemblyInformationalVersion("1.4")]

internal static class InstallerProgram {
    [STAThread] static int Main(string[] args) {
        AppContext.SetSwitch("Switch.System.IO.UseLegacyPathHandling",false);
        AppContext.SetSwitch("Switch.System.IO.BlockLongPaths",false);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (args.Length == 0) { Application.Run(new InstallerWizard()); return 0; }
        string logPath = null;
        try {
            if (args.Length == 2 && args[0] == "--render-preview") {
                using (var wizard = new InstallerWizard()) {
                    wizard.SetPreviewPaths();
                    wizard.ShowInTaskbar = false;
                    wizard.StartPosition = FormStartPosition.Manual;
                    wizard.Location = new Point(-20000, -20000);
                    wizard.Show(); Application.DoEvents();
                    using (var image = new Bitmap(wizard.Width, wizard.Height)) {
                        wizard.DrawToBitmap(image, new Rectangle(0,0,image.Width,image.Height));
                        image.Save(Path.GetFullPath(args[1]), System.Drawing.Imaging.ImageFormat.Png);
                    }
                    wizard.Close();
                }
                return 0;
            }
            string mode = args[0];
            if (mode != "--check" && mode != "--apply" && mode != "--recover" && mode != "--uninstall" && mode != "--uninstall-check")
                throw new ArgumentException("Use the wizard without arguments, or --check/--apply --game PATH --mods PATH --active-mods PATH --log FILE; recovery additionally requires --backup PATH.");
            var options = new Dictionary<string,string>(StringComparer.Ordinal);
            for (int i=1; i<args.Length; i+=2) {
                if (i+1 >= args.Length || !new[]{"--game","--mods","--active-mods","--log","--backup"}.Contains(args[i]) || options.ContainsKey(args[i]))
                    throw new ArgumentException("Invalid or repeated command-line option.");
                options.Add(args[i],args[i+1]);
            }
            if (!options.ContainsKey("--game") || !options.ContainsKey("--mods") || !options.ContainsKey("--active-mods") || !options.ContainsKey("--log"))
                throw new ArgumentException("Headless mode requires --game, --mods, --active-mods and --log.");
            logPath = Path.GetFullPath(options["--log"]);
            // Never silently replace an existing log or another user file.
            using (var file = new FileStream(logPath, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
            using (var writer = new StreamWriter(file, new UTF8Encoding(false))) {
                writer.AutoFlush = true;
                Action<string> log = line => writer.WriteLine(DateTime.UtcNow.ToString("o")+" "+line);
                log("HDC 1.4 | Developer: Hina | unsigned community installer");
                try {
                    LineupInstallerCore.Report report;
                    if (mode == "--recover") {
                        if (!options.ContainsKey("--backup")) throw new ArgumentException("Recovery requires --backup.");
                        report = LineupInstallerCore.Recover(options["--game"], options["--mods"],options["--backup"],options["--active-mods"],log);
                    } else if(mode=="--uninstall"||mode=="--uninstall-check") { report=mode=="--uninstall"?LineupInstallerCore.Uninstall(options["--game"],options["--mods"],options["--active-mods"],log):LineupInstallerCore.UninstallCheck(options["--game"],options["--mods"],options["--active-mods"],log); } else using (var payload = EmbeddedPayload.Extract(log)) {
                        report = mode == "--check" ? LineupInstallerCore.Check(options["--game"],options["--mods"],payload.Path,options["--active-mods"],log)
                            : LineupInstallerCore.Apply(options["--game"],options["--mods"],payload.Path,options["--active-mods"],log);
                    }
                    log("RESULT success="+report.Success+" applied="+report.Applied+" backend="+report.BackendId+" files="+report.ChangedFileCount+" package="+report.PackageMode);
                    return report.Success ? 0 : 1;
                } catch (Exception e) { log("FAILED: "+e.Message); return 1; }
            }
        } catch (Exception e) {
            MessageBox.Show(e.Message, "HDC installer",MessageBoxButtons.OK,MessageBoxIcon.Error); return 2;
        }
    }

    [DllImport("shell32.dll")] static extern int SHGetKnownFolderPath([MarshalAs(UnmanagedType.LPStruct)] Guid id,uint flags,IntPtr token,out IntPtr path);
    internal static string DefaultMods() {
        IntPtr path=IntPtr.Zero;
        try {
            if (SHGetKnownFolderPath(new Guid("4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4"),0,IntPtr.Zero,out path)==0)
                return System.IO.Path.Combine(Marshal.PtrToStringUni(path),"ACE","mods");
        } finally { if(path!=IntPtr.Zero) Marshal.FreeCoTaskMem(path); }
        return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),"Saved Games","ACE","mods");
    }
    internal static string DefaultGame() {
        var libraries=new List<string>();
        try { using(var k=Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam")) if(k!=null) {
            var s=k.GetValue("SteamPath") as string; if(!String.IsNullOrEmpty(s))libraries.Add(s);
        }} catch { }
        libraries.Add(System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),"Steam"));
        foreach(string lib in libraries.ToArray()) try {
            string manifest=System.IO.Path.Combine(lib,"steamapps","libraryfolders.vdf");
            if(File.Exists(manifest)) foreach(Match m in Regex.Matches(File.ReadAllText(manifest),"\"path\"\\s+\"([^\"]+)\""))
                libraries.Add(m.Groups[1].Value.Replace(@"\\",@"\"));
        } catch { }
        foreach(string lib in libraries.Distinct(StringComparer.OrdinalIgnoreCase)) {
            string game=System.IO.Path.Combine(lib,"steamapps","common","Assetto Corsa EVO");
            if(File.Exists(System.IO.Path.Combine(game,"AssettoCorsaEVO.exe")) && File.Exists(System.IO.Path.Combine(game,"content.kspkg")))return game;
        }
        return "";
    }
    internal static string RememberedMods() {
        try {
            string file=System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Hina","HDC","storage.txt");
            if(File.Exists(file)) {
                string path=File.ReadAllText(file).Trim();
                if(!String.IsNullOrWhiteSpace(path)&&System.IO.Path.IsPathRooted(path)&&path.IndexOfAny(new[]{'\r','\n','\0'})<0)return path;
            }
        }catch { }
        return DefaultMods();
    }
    internal static void RememberMods(string path) {
        string directory=System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Hina","HDC");
        Directory.CreateDirectory(directory);
        File.WriteAllText(System.IO.Path.Combine(directory,"storage.txt"),System.IO.Path.GetFullPath(path),new UTF8Encoding(false));
    }
}

internal sealed class EmbeddedPayload : IDisposable {
    internal string Path {get;private set;}
    static string Hash(Stream input) { using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(input)).Replace("-","").ToLowerInvariant(); }
    internal static EmbeddedPayload Extract(Action<string> log) {
        log("Checking the release payload...");
        using(var stream=new FileStream(System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory,PayloadIdentity.FileName),FileMode.Open,FileAccess.Read,FileShare.Read)) {
            if(stream==null || Hash(stream)!=PayloadIdentity.Sha256)throw new InvalidDataException("The release payload checksum does not match. Extract the complete release again; keep its payload ZIP beside this installer.");
            stream.Position=0;
            string root=System.IO.Path.Combine(System.IO.Path.GetTempPath(),"HDC_Release_"+Guid.NewGuid().ToString("N"));
            var payload=new EmbeddedPayload{Path=root};
            try {
                using(var zip=new ZipArchive(stream,ZipArchiveMode.Read,true)) {
                    if(zip.Entries.Count!=PayloadIdentity.FileCount)throw new InvalidDataException("Unexpected release file count.");
                    long total=0;var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                    foreach(var entry in zip.Entries) {
                        ValidateName(entry.FullName);
                        if(!names.Add(entry.FullName))throw new InvalidDataException("Duplicate release file.");
                        if(((entry.ExternalAttributes>>16)&0xf000)==0xa000)throw new InvalidDataException("Links are not allowed in the release.");
                        if(entry.Length<0 || entry.Length>PayloadIdentity.MaxFileBytes)throw new InvalidDataException("Invalid release file size.");
                        total=checked(total+entry.Length);
                    }
                    if(total!=PayloadIdentity.TotalBytes)throw new InvalidDataException("Unexpected release size.");
                    var drive=new DriveInfo(System.IO.Path.GetPathRoot(root));
                    if(drive.IsReady && drive.AvailableFreeSpace<total+32L*1024*1024)throw new IOException("Not enough temporary disk space to unpack Ronin Pass and the included cars.");
                    CheckParents(root);Directory.CreateDirectory(root);CheckParents(root);
                    log("Unpacking HDC 1.4 and the included cars...");
                    long unpacked=0,nextProgress=512L*1024*1024;
                    foreach(var entry in zip.Entries) {
                        string destination=System.IO.Path.GetFullPath(System.IO.Path.Combine(root,entry.FullName.Replace('/',System.IO.Path.DirectorySeparatorChar)));
                        if(!destination.StartsWith(root+System.IO.Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Unsafe release path.");
                        CheckParents(destination);Directory.CreateDirectory(System.IO.Path.GetDirectoryName(destination));CheckParents(destination);
                        using(var source=entry.Open())using(var target=new FileStream(destination,FileMode.CreateNew,FileAccess.Write,FileShare.None)) {
                            byte[] buffer=new byte[65536];long copied=0;int count;
                            while((count=source.Read(buffer,0,buffer.Length))>0) {
                                copied=checked(copied+count);if(copied>entry.Length)throw new InvalidDataException("Release file exceeded its declared size.");
                                target.Write(buffer,0,count);
                            }
                            if(copied!=entry.Length)throw new InvalidDataException("Incomplete release file.");
                            unpacked+=copied;if(unpacked>=nextProgress){log("Unpacking track + car: "+(100*unpacked/total)+"%");nextProgress=unpacked+512L*1024*1024;}
                        }
                    }
                }
                return payload;
            } catch {payload.Dispose();throw;}
        }
    }
    static void ValidateName(string name) {
        if(String.IsNullOrEmpty(name)||System.IO.Path.IsPathRooted(name)||name.IndexOfAny(new[]{'\\',':','\0','\r','\n'})>=0)throw new InvalidDataException("Unsafe release filename.");
        foreach(string part in name.Split('/')) {
            if(part.Length==0||part=="."||part==".."||part.EndsWith(".")||part.EndsWith(" ")||part.IndexOfAny(System.IO.Path.GetInvalidFileNameChars())>=0||Regex.IsMatch(part.Split('.')[0],"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$",RegexOptions.IgnoreCase))throw new InvalidDataException("Unsafe release filename.");
        }
    }
    static void CheckParents(string path) {
        while(!String.IsNullOrEmpty(path)) {
            if((File.Exists(path)||Directory.Exists(path))&&(File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new IOException("A link occupies a temporary extraction path.");
            string parent=System.IO.Path.GetDirectoryName(path);if(parent==path)break;path=parent;
        }
    }
    static void CleanDirectory(string root,string directory) {
        if(!directory.Equals(root,StringComparison.OrdinalIgnoreCase)&&!directory.StartsWith(root+System.IO.Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("Unsafe cleanup path.");
        if((File.GetAttributes(directory)&FileAttributes.ReparsePoint)!=0)throw new IOException("A link occupies a temporary directory.");
        foreach(string file in Directory.GetFiles(directory)) {
            if((File.GetAttributes(file)&FileAttributes.ReparsePoint)!=0)throw new IOException("A link occupies a temporary file.");
            File.Delete(file);
        }
        foreach(string dir in Directory.GetDirectories(directory))CleanDirectory(root,dir);
        Directory.Delete(directory,false);
    }
    public void Dispose() {
        if(Path==null)return;
        string root=System.IO.Path.GetFullPath(Path);
        string parent=System.IO.Path.GetFullPath(System.IO.Path.GetTempPath()).TrimEnd('\\','/');
        try {if(System.IO.Path.GetDirectoryName(root).Equals(parent,StringComparison.OrdinalIgnoreCase)&&Regex.IsMatch(System.IO.Path.GetFileName(root),"^HDC_Release_[0-9a-f]{32}$")&&Directory.Exists(root))CleanDirectory(root,root);}catch { /* Only our unique staging directory may remain for manual cleanup. */ }
        Path=null;
    }
}

internal sealed class BrandPanel : Panel {
    readonly Image logo,photo;
    internal BrandPanel() {
        DoubleBuffered=true;BackColor=Color.FromArgb(11,13,17);
        logo=Load("Product.Logo.png");photo=Load("Product.Photo.png");
    }
    static Image Load(string name){using(var s=Assembly.GetExecutingAssembly().GetManifestResourceStream(name))using(var b=Image.FromStream(s))return new Bitmap(b);}
    protected override void OnPaint(PaintEventArgs e) {
        base.OnPaint(e);var g=e.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias;g.InterpolationMode=InterpolationMode.HighQualityBicubic;
        float scale=Width/340f;g.ScaleTransform(scale,scale);
        // The original logo is drawn directly. No alterations to the HTC mark.
        g.DrawImage(logo,new Rectangle(23,0,294,294));
        using(var title=new Font("Segoe UI",39,FontStyle.Bold|FontStyle.Italic,GraphicsUnit.Pixel))g.DrawString("THE YARD",title,Brushes.White,new PointF(24,273));
        using(var body=new Font("Segoe UI",13.33f,FontStyle.Regular,GraphicsUnit.Pixel)) {
            using(var b=new SolidBrush(Color.FromArgb(195,202,214)))g.DrawString("HINA'S DRIFT CLUB  /  UPDATE 1.4",body,b,new PointF(29,334));
        }
        using(var accent=new SolidBrush(Color.FromArgb(226,59,69)))g.FillRectangle(accent,29,372,51,3);
        float ratio=photo.Width/(float)photo.Height;
        int height=(int)(340/ratio);
        g.DrawImage(photo,new Rectangle(0,413,340,height));
        using(var gradient=new LinearGradientBrush(new Rectangle(0,413,340,height),Color.FromArgb(25,11,13,17),Color.FromArgb(85,11,13,17),90))g.FillRectangle(gradient,0,413,340,height);

    }
    protected override void Dispose(bool disposing){if(disposing){logo.Dispose();photo.Dispose();}base.Dispose(disposing);}
}

internal sealed class InstallerWizard : Form {
    readonly TextBox gameBox=new TextBox(),modsBox=new TextBox(),details=new TextBox();
    readonly Button install=new Button(),check=new Button(),recover=new Button(),close=new Button(),uninstall=new Button();
    readonly Label status=new Label();readonly ProgressBar progress=new ProgressBar();
    readonly List<Control> inputs=new List<Control>();bool busy;
    static readonly Color Bg=Color.FromArgb(20,23,29),Muted=Color.FromArgb(159,172,190),Red=Color.FromArgb(219,53,66);
    internal InstallerWizard() {
        SuspendLayout();
        Icon=System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath);ShowIcon=true;ShowInTaskbar=true;
        Text="HDC 1.4 | Hina's Drift Club";ClientSize=new Size(1000,716);FormBorderStyle=FormBorderStyle.FixedSingle;MaximizeBox=false;
        StartPosition=FormStartPosition.CenterScreen;BackColor=Bg;ForeColor=Color.White;Font=new Font("Segoe UI",10);AutoScaleMode=AutoScaleMode.None;
        Controls.Add(new BrandPanel{Location=new Point(0,0),Size=new Size(340,716)});
        LabelAt("HDC  /  TRACK + CARS INSTALLER",376,31,590,20,9,FontStyle.Bold,Muted);
        LabelAt("Welcome to HDC",374,65,600,46,27,FontStyle.Bold,Color.White);
        LabelAt("The Yard and all six HDC cars.",376,125,582,26,11,FontStyle.Regular,Muted);
        Controls.Add(new Panel{BackColor=Color.FromArgb(48,55,66),Location=new Point(376,165),Size=new Size(586,1)});
        FolderRow("ASSETTO CORSA EVO FOLDER",gameBox,197,InstallerProgram.DefaultGame());
        LabelAt("Choose the folder containing AssettoCorsaEVO.exe.",376,261,580,22,9,FontStyle.Regular,Muted);
        FolderRow("MODS STORAGE FOLDER",modsBox,303,InstallerProgram.RememberedMods());
        LabelAt("Track storage can be linked. Cars install to EVO's active mods folder.",376,368,580,32,9,FontStyle.Regular,Muted);
        var card=new Panel{BackColor=Color.FromArgb(29,34,43),Location=new Point(376,412),Size=new Size(586,87)};
        card.Controls.Add(new Label{Text="THE YARD  +  SIX CARS  +  SUPPORTED SETUPS",Location=new Point(16,14),Size=new Size(550,24),Font=new Font("Segoe UI",10,FontStyle.Bold),ForeColor=Color.White});
        card.Controls.Add(new Label{Text="Close EVO, the SDK and EvoForge before installing.",Location=new Point(16,47),Size=new Size(550,24),Font=new Font("Segoe UI",10),ForeColor=Muted});Controls.Add(card);
        status.SetBounds(376,517,586,22);status.Text="Ready when you are.";status.ForeColor=Color.White;Controls.Add(status);
        progress.SetBounds(376,547,586,4);progress.Style=ProgressBarStyle.Continuous;Controls.Add(progress);
        details.SetBounds(376,565,586,59);details.Multiline=true;details.ReadOnly=true;details.ScrollBars=ScrollBars.Vertical;details.BorderStyle=BorderStyle.None;details.BackColor=Bg;details.ForeColor=Muted;details.Font=new Font("Segoe UI",9);details.Text="Developer: Hina  |  Unsigned community release\r\nOriginal files are backed up before changes.";Controls.Add(details);
        Configure(recover,"Recovery",376,650,95,false);Configure(check,"Check",479,650,74,false);Configure(uninstall,"Uninstall",561,650,99,false);Configure(close,"Close",668,650,74,false);Configure(install,"Install / Update",750,650,212,true);
        uninstall.Click+=async(s,e)=>{if(MessageBox.Show(this,"Remove HDC 1.4 content from the selected folders? Other products and transaction backups are kept.","Uninstall HDC 1.4",MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes)await Run("uninstall",null);};
        check.Click+=async (s,e)=>await Run("check",null);install.Click+=async(s,e)=>await Run("install",null);close.Click+=(s,e)=>Close();
        recover.Click+=async(s,e)=>{using(var picker=new FolderBrowserDialog{Description="Select the HDC_Backups session folder named in the recovery message.",ShowNewFolderButton=false}) {
            string backupRoot=System.IO.Path.Combine(gameBox.Text.Trim(),"HDC_Backups");if(Directory.Exists(backupRoot))picker.SelectedPath=backupRoot;
            if(picker.ShowDialog(this)==DialogResult.OK)await Run("recover",picker.SelectedPath);
        }};
        FormClosing+=(s,e)=>{if(busy){e.Cancel=true;status.Text="Please let the installation or recovery finish.";}};
        AcceptButton=install;CancelButton=close;
        ResumeLayout(false);
        using(var graphics=CreateGraphics()) {
            float scale=graphics.DpiX/96f;
            if(Math.Abs(scale-1)>0.01f)Scale(new SizeF(scale,scale));
            // Keep every control reachable on smaller high-DPI displays.
            AutoScrollMinSize=ClientSize;AutoScroll=true;
            Rectangle screen=Screen.FromControl(this).WorkingArea;
            Size=new Size(Math.Min(Width,screen.Width),Math.Min(Height,screen.Height));
        }
    }
    internal void SetPreviewPaths(){gameBox.Text=@"D:\SteamLibrary\steamapps\common\Assetto Corsa EVO";modsBox.Text=@"C:\Users\Player\Saved Games\ACE\mods";}
    void LabelAt(string text,int x,int y,int w,int h,float size,FontStyle style,Color color){Controls.Add(new Label{Text=text,Location=new Point(x,y),Size=new Size(w,h),Font=new Font("Segoe UI",size,style),ForeColor=color,BackColor=Bg});}
    void FolderRow(string name,TextBox box,int y,string initial) {
        LabelAt(name,376,y,580,22,9,FontStyle.Bold,Muted);box.SetBounds(376,y+29,487,28);box.Font=new Font("Segoe UI",10);box.BackColor=Color.FromArgb(30,35,44);box.ForeColor=Color.White;box.BorderStyle=BorderStyle.FixedSingle;box.Text=initial;Controls.Add(box);inputs.Add(box);
        var browse=new Button();Configure(browse,"Browse...",874,y+26,88,false);browse.Height=32;inputs.Add(browse);
        browse.Click+=(s,e)=>{using(var dialog=new FolderBrowserDialog{Description=name,ShowNewFolderButton=box==modsBox}){if(Directory.Exists(box.Text))dialog.SelectedPath=box.Text;if(dialog.ShowDialog(this)==DialogResult.OK)box.Text=dialog.SelectedPath;}};
    }
    void Configure(Button button,string text,int x,int y,int width,bool primary){button.SetBounds(x,y,width,40);button.Text=text;button.FlatStyle=FlatStyle.Flat;button.FlatAppearance.BorderSize=primary?0:1;button.FlatAppearance.BorderColor=Color.FromArgb(73,83,99);button.BackColor=primary?Red:Bg;button.ForeColor=Color.White;button.Font=new Font("Segoe UI",10,primary?FontStyle.Bold:FontStyle.Regular);button.Cursor=Cursors.Hand;Controls.Add(button);}
    void Log(string message){if(IsDisposed)return;if(InvokeRequired){BeginInvoke(new Action<string>(Log),message);return;}details.AppendText("\r\n"+message);details.SelectionStart=details.TextLength;details.ScrollToCaret();status.Text=message.Length>88?message.Substring(0,85)+"...":message;}
    async Task Run(string mode,string backup) {
        if(busy)return;string game=gameBox.Text.Trim(),mods=modsBox.Text.Trim();
        if(String.IsNullOrWhiteSpace(game)||String.IsNullOrWhiteSpace(mods)){MessageBox.Show(this,"Choose both the EVO game folder and its mods folder.","Choose installation folders",MessageBoxButtons.OK,MessageBoxIcon.Information);return;}
        busy=true;foreach(var c in inputs)c.Enabled=false;install.Enabled=check.Enabled=recover.Enabled=uninstall.Enabled=close.Enabled=false;progress.Style=ProgressBarStyle.Marquee;details.Clear();
        try {
            var report=await Task.Run(()=>{
                string active=InstallerProgram.DefaultMods();
                Log("EVO active mods folder: "+active);
                if(mode=="recover")return LineupInstallerCore.Recover(game,mods,backup,active,Log);
                if(mode=="uninstall")return LineupInstallerCore.Uninstall(game,mods,active,Log);
                using(var payload=EmbeddedPayload.Extract(Log))return mode=="check"?LineupInstallerCore.Check(game,mods,payload.Path,active,Log):LineupInstallerCore.Apply(game,mods,payload.Path,active,Log);
            });
            progress.Style=ProgressBarStyle.Continuous;progress.Value=100;
            if(mode=="check")status.Text="Checks passed. Ready to install.";
            else if(mode=="recover")status.Text="Recovery complete. Original files restored.";
            else if(mode=="uninstall")status.Text="Uninstall complete. Other products and backups preserved.";
            else {
                try{InstallerProgram.RememberMods(mods);}catch(Exception e){Log("Installed successfully; could not remember the storage folder: "+e.Message);}
                install.Text="Install / Update";Log("The Yard and all six HDC cars are ready. Reselect the track/car before loading.");status.Text="HDC 1.4 and included cars are ready.";
            }
        } catch(Exception e) {
            progress.Style=ProgressBarStyle.Continuous;progress.Value=0;Log("Stopped: "+e.Message);status.Text="Could not complete. See the details below.";
            MessageBox.Show(this,e.Message,"HDC installer",MessageBoxButtons.OK,MessageBoxIcon.Error);
        } finally {busy=false;foreach(var c in inputs)c.Enabled=true;install.Enabled=check.Enabled=recover.Enabled=uninstall.Enabled=close.Enabled=true;}
    }
}
