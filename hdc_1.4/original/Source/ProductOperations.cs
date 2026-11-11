// Scoped release additions to the existing transactional track installer.
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Collections.Generic;
using System.Threading;

public static partial class LineupInstallerCore {
    static bool Removing;
    static readonly object OperationLock = new object();
    sealed class ReleaseMutex : IDisposable {
        readonly Mutex mutex;bool acquired;
        internal ReleaseMutex(string game) {
            string key=Hash(Encoding.UTF8.GetBytes(PhysicalPath(game).TrimEnd('\\','/').ToUpperInvariant()));
            mutex=new Mutex(false,"Local\\HinaEvoRelease_"+key);
            try {try{acquired=mutex.WaitOne(0,false);}catch(AbandonedMutexException){acquired=true;}
                Need(acquired,"Another Hina installer is using this game folder. Let it finish before continuing.");
            }catch{mutex.Dispose();throw;}
        }
        public void Dispose(){if(acquired){acquired=false;mutex.ReleaseMutex();}mutex.Dispose();}
    }
    static Report Execute(string game,string mods,string payload,string active,Action<string> log,bool apply) {
        lock(OperationLock){using(var lease=new ReleaseMutex(game))return ExecuteCore(game,mods,payload,active,log,apply);}
    }
    public static Report Recover(string game,string mods,string backup,string active,Action<string> log) {
        lock(OperationLock){using(var lease=new ReleaseMutex(game))return RecoverCore(game,mods,backup,active,log);}
    }
    static partial void AdditionalPaths(HashSet<string> paths) { foreach(string p in ProductModsPaths) paths.Add(p); }
    static partial void ValidateAdditionalState(string activeMods) { }
    static HashSet<string> GamePaths() { return new HashSet<string>(ProductGamePaths, StringComparer.OrdinalIgnoreCase); }
    static bool OwnCarRelative(string rel) { return ProductCarIds.Any(id => rel.StartsWith("content/cars/"+id+"/", StringComparison.OrdinalIgnoreCase)); }
    static bool OwnUiRelative(string rel) { return ProductUiRoots.Any(root => rel.StartsWith(root+"/",StringComparison.OrdinalIgnoreCase)); }
    static bool OwnedModsRelative(string rel) { return rel.StartsWith(TrackRoot+"/",StringComparison.OrdinalIgnoreCase) || BundlePaths().Contains(rel) || UiPaths().Contains(rel) || OwnCarRelative(rel) || OwnUiRelative(rel); }

    // These are the reviewed HDC native directory ownership checks, shared by
    // the two product bundles. Mixed/native/foreign packages are never pruned.
    sealed class BundleIdentity {
        public HashSet<string> Owned = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        public string PureId;
        public bool HasForeign;
    }
    static BundleIdentity ReadBundleIdentity(string file) {
        CheckReparse(file); var result = new BundleIdentity();
        using(var stream = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.Read)) {
            if(stream.Length < FooterSize) return result;
            long footer=stream.Length-FooterSize;stream.Position=footer;
            var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);byte[] raw=new byte[256];bool ended=false;
            for(int record=0;record<FooterSize/256;record++) {
                int read=0;while(read<256){int count=stream.Read(raw,read,256-read);Need(count>0,"Truncated native car directory: "+file);read+=count;}
                byte[] entry=Xor(raw);if(BitConverter.ToUInt64(entry,232)==0){ended=true;break;}
                int length=BitConverter.ToUInt16(entry,230);Need(length>=1&&length<=224,"Invalid native package directory name: "+file);
                string name=Normalize(new UTF8Encoding(false,true).GetString(entry,0,length));
                Need(names.Add(name)&&!name.StartsWith("/")&&!name.Split('/').Any(s=>s==".."||s=="."||s.Length==0),"Ambiguous native package directory: "+file);
                long size=BitConverter.ToInt64(entry,240),offset=BitConverter.ToInt64(entry,248);
                Need(size>=0&&offset>=0&&offset<=footer-size,"Native package resource is outside its payload: "+file);
                string id=ProductCarIds.FirstOrDefault(candidate=>name=="content/cars/"+candidate||name.StartsWith("content/cars/"+candidate+"/",StringComparison.Ordinal));
                if(id==null)result.HasForeign=true;else result.Owned.Add(id);
            }
            // Foreign invalid/unrecognized packages must not become our cleanup targets.
            if(result.Owned.Count>0)Need(ended,"Unterminated owned native car directory.");
        }
        if(result.Owned.Count==1&&!result.HasForeign)result.PureId=result.Owned.First();return result;
    }
    static string ProductSnapshot(string active) {
        var rows=new List<string>();
        if(Directory.Exists(active))foreach(string file in Directory.GetFiles(active,"*.kspkg",SearchOption.TopDirectoryOnly)) {
            var id=ReadBundleIdentity(file);
            rows.Add(Path.GetFileName(file).ToLowerInvariant()+"|"+new FileInfo(file).Length+"|"+id.PureId+"|"+String.Join(",",id.Owned.OrderBy(x=>x)));
        }
        foreach(string id in ProductCarIds){string root=Within(active,"content/cars/"+id);Need(!File.Exists(root),"A file occupies a car resource directory.");if(Directory.Exists(root))foreach(string file in EnumerateSafe(root))rows.Add(file.ToLowerInvariant()+"|"+HashFile(file));}
        return FingerprintRecords(rows);
    }
    static void ValidateProductSnapshot(Plan p) { Need(ProductSnapshot(p.ActiveMods)==p.BundleBeforeSnapshot,"Car identities or development files changed during planning."); }
    static bool Marker(string game,string rel,string expected) {
        string file=Within(game,rel);Need(!Directory.Exists(file),"A directory occupies a runtime marker.");
        if(!File.Exists(file))return false;
        Need(File.ReadAllBytes(file).SequenceEqual(Encoding.ASCII.GetBytes(expected)),"Unrecognized shared runtime ownership marker: "+rel);return true;
    }
    static bool OtherRuntimeNeeded(string game) {
        return ProductHasRuntime && Marker(game,"HinaRuntime/HSC.enabled","HSC-CHARACTER-1\n");
    }
    static bool PreserveInputProxy(string game) {
        return OtherRuntimeNeeded(game) || HashFile(Within(game,"dinput8.dll"))==LegacyHscHash;
    }
    static void ValidateRuntimeBefore(Plan p) {
        if(!ProductHasRuntime)return;
        OtherRuntimeNeeded(p.Game);
        foreach(string rel in ProductGamePaths) {
            string target=Within(p.Game,rel);if(!File.Exists(target))continue;
            string actual=HashFile(target);string[] allowed;
            Need(RuntimeKnownHashes.TryGetValue(rel,out allowed)&&allowed.Contains(actual,StringComparer.Ordinal),"Unrecognized runtime file must be preserved before installation: "+rel);
            if(!Removing&&rel=="dinput8.dll"&&actual==LegacyHscHash)
                throw new InvalidOperationException("Upgrade HSC to b0.2 first. Its older loader and ownership record must migrate together; the existing HSC installation was preserved.");
        }
        string bank=Within(p.ActiveMods,"content/sfx/wheel.bank");
        if(File.Exists(bank)){string[] allowed;Need(RuntimeKnownHashes.TryGetValue("mods/content/sfx/wheel.bank",out allowed)&&allowed.Contains(HashFile(bank),StringComparer.Ordinal),"Another sound mod owns wheel.bank; it was preserved.");}
    }
    static FilePlan OwnedDelete(string root,string rel,bool nativeCar=false) {
        Need(OwnedModsRelative(rel)||GamePaths().Contains(rel)||(nativeCar&&rel.IndexOf('/')<0&&rel.EndsWith(".kspkg",StringComparison.OrdinalIgnoreCase)),"Cleanup escaped product ownership.");
        string target=Within(root,rel);Need(File.Exists(target)&&!Directory.Exists(target),"Cleanup target changed: "+rel);
        if(nativeCar)Need(ReadBundleIdentity(target).PureId!=null,"Only a pure owned native car can be retired.");
        string temp=target+".akagi-firstpass01-installing";CheckReparse(temp);Need(!File.Exists(temp)&&!Directory.Exists(temp),"An interrupted file needs recovery.");
        return new FilePlan{Root=root,Relative=rel,Target=target,Existed=true,Changed=true,Delete=true,BeforeHash=HashFile(target),BeforeLength=new FileInfo(target).Length,AfterHash="-",AfterLength=0};
    }
    static void ProductPlans(Plan p) {
        p.BundleBeforeSnapshot=ProductSnapshot(p.ActiveMods);ValidateRuntimeBefore(p);
        var deletes=new List<FilePlan>();
        if(!Removing)for(int i=0;i<ProductCarIds.Length;i++)Need(ReadBundleIdentity(Within(p.Payload,ProductPackages[i])).PureId==ProductCarIds[i],"Bundled car identity differs: "+ProductPackages[i]);
        if(Directory.Exists(p.ActiveMods))foreach(string file in Directory.GetFiles(p.ActiveMods,"*.kspkg",SearchOption.TopDirectoryOnly)) {
            string name=Path.GetFileName(file);var identity=ReadBundleIdentity(file);int destination=Array.FindIndex(ProductPackages,n=>n.Equals(name,StringComparison.OrdinalIgnoreCase));
            Need(identity.Owned.Count==0||identity.PureId!=null,"A package mixes this product with other content; preserve it outside active mods first: "+name);
            if(destination>=0)Need(identity.PureId==ProductCarIds[destination],"A release destination contains a different package: "+name);
            if(identity.PureId!=null&&(Removing||destination<0))deletes.Add(OwnedDelete(p.ActiveMods,name,true));
        }
        // Back up and retire loose development resources only in exact owned car/UI namespaces.
        foreach(string relativeRoot in ProductCarIds.Select(id=>"content/cars/"+id).Concat(ProductUiRoots)) {
            string root=Within(p.ActiveMods,relativeRoot);Need(!File.Exists(root),"A file occupies an owned resource directory.");
            if(!Directory.Exists(root))continue;
            foreach(string file in EnumerateSafe(root)){string rel=relativeRoot+"/"+file.Substring(root.Length+1).Replace('\\','/');if(Removing||!p.Checksums.ContainsKey(rel))deletes.Add(OwnedDelete(p.ActiveMods,rel));}
        }
        if(Removing) {
            foreach(string root in new[]{p.Mods,p.ActiveMods}.Distinct(StringComparer.OrdinalIgnoreCase))foreach(string rel in UiPaths())if(File.Exists(Within(root,rel)))deletes.Add(OwnedDelete(root,rel));
            foreach(string rel in BundlePaths())if(!ProductPackages.Contains(rel,StringComparer.OrdinalIgnoreCase)&&!OwnUiRelative(rel)&&File.Exists(Within(p.ActiveMods,rel)))deletes.Add(OwnedDelete(p.ActiveMods,rel));
            foreach(string rel in ProductGamePaths)if(File.Exists(Within(p.Game,rel))&&!(rel=="dinput8.dll"&&PreserveInputProxy(p.Game)))deletes.Add(OwnedDelete(p.Game,rel));
        } else {
            foreach(string rel in ProductGamePaths){string payloadRel=ProductGamePayload[rel];p.Files.Add(PlanFile(p.Game,rel,Within(p.Payload,payloadRel),null,p.Checksums[payloadRel]));}
        }
        p.Files.InsertRange(0,deletes);p.Report.ObsoleteFileCount+=deletes.Count;ValidateProductSnapshot(p);
    }
    static void ValidateProductInstalled(Plan p) {
        if(!Removing)foreach(string rel in BundlePaths())Need(File.Exists(Within(p.ActiveMods,rel))&&HashFile(Within(p.ActiveMods,rel))==p.Checksums[rel],"Installed bundle differs: "+rel);
        if(Directory.Exists(p.ActiveMods))foreach(string file in Directory.GetFiles(p.ActiveMods,"*.kspkg",SearchOption.TopDirectoryOnly)) {
            var id=ReadBundleIdentity(file);if(id.Owned.Count==0)continue;
            Need(!Removing&&id.PureId!=null,"Owned or mixed car remains after uninstall.");int i=Array.IndexOf(ProductCarIds,id.PureId);
            Need(Path.GetFileName(file).Equals(ProductPackages[i],StringComparison.OrdinalIgnoreCase),"A duplicate car appeared during installation.");
        }
        foreach(string id in ProductCarIds){string root=Within(p.ActiveMods,"content/cars/"+id);Need(!Directory.Exists(root)||!EnumerateSafe(root).Any(),"Loose development car resources remain.");}
    }
    static bool RecoveryOwned(string backup,int index,string rootKind,string rel,string state,string after,string mods,string active) {
        if(rootKind=="game")return rel=="content_files.txt"||GamePaths().Contains(rel);
        bool activeRoot=rootKind=="active"||(rootKind=="mods"&&mods.Equals(active,StringComparison.OrdinalIgnoreCase));
        if(rootKind=="mods"&&rel.StartsWith(TrackRoot+"/",StringComparison.OrdinalIgnoreCase))return true;
        if(UiPaths().Contains(rel))return true;
        if(!activeRoot)return false;
        if(OwnedModsRelative(rel))return true;
        if(after!="-"||state!="REPLACED"||rel.IndexOf('/')>=0||!rel.EndsWith(".kspkg",StringComparison.OrdinalIgnoreCase))return false;
        string original=Within(backup,"files/"+index+".before");return File.Exists(original)&&ReadBundleIdentity(original).PureId!=null;
    }
    static void ValidateRollbackFile(FilePlan f) {
        CheckReparse(f.Target);Need(!Directory.Exists(f.Target),"Rollback target became a directory.");
        Need(!f.Existed||f.Delete||File.Exists(f.Target),"A pre-existing target was removed; recovery refused.");
        if(File.Exists(f.Target)){string h=HashFile(f.Target);Need(h==f.AfterHash||(f.Existed&&h==f.BeforeHash),"A target was edited; recovery refused: "+f.Relative);}
        string temp=f.Target+".akagi-firstpass01-installing";CheckReparse(temp);Need(!Directory.Exists(temp),"Recovery temporary became a directory.");
        if(File.Exists(temp)){string h=HashFile(temp);Need(h==f.AfterHash||h==f.BeforeHash,"An unknown partial temporary was preserved: "+f.Relative);}
    }
    public static Report Uninstall(string game,string mods,string activeMods,Action<string> log) {
        lock(OperationLock){Need(!Removing,"Another operation is active.");Removing=true;try{return Execute(game,mods,Path.GetTempPath(),activeMods,log,true);}finally{Removing=false;}}
    }
    public static Report UninstallCheck(string game,string mods,string activeMods,Action<string> log) {
        lock(OperationLock){Need(!Removing,"Another operation is active.");Removing=true;try{return Execute(game,mods,Path.GetTempPath(),activeMods,log,false);}finally{Removing=false;}}
    }
}
