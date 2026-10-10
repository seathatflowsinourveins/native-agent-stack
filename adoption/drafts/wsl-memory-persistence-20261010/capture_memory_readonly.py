#!/usr/bin/env python3
"""Read only the CC-designated memory inputs; print masked JSON to stdout."""
import subprocess,json,hashlib,re,configparser
from pathlib import Path
def timed(cmd,env=None):
 start=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
 p=subprocess.run(cmd,env=env,capture_output=True)
 end=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
 def dec(x):return x.decode('utf-16le' if b'\x00' in x else 'utf-8',errors='replace').lstrip('\ufeff')
 return {'command':cmd,'start_utc':start,'end_utc':end,'exit_code':p.returncode,'stdout':dec(p.stdout),'stderr':dec(p.stderr)}
out={'evidence_class':'native_proven','mutations':[]}
out['linux']=[timed(['systemctl','show','user-1000.slice','--property=MemoryMax,MemoryHigh,EffectiveMemoryMax,EffectiveMemoryHigh,ControlGroup,FragmentPath,DropInPaths']),timed(['sysctl','vm.swappiness']),timed(['systemctl','--version']),timed(['uname','-r']),timed(['/mnt/c/Windows/System32/wsl.exe','--version'])]
cg=Path('/sys/fs/cgroup')
out['cgroups']={'observed_at_utc':subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),'values':{str(p.relative_to(cg)):p.read_text().strip() for d in ['', 'non-systemd','user.slice','user.slice/user-1000.slice'] for n in ['memory.max','memory.high','memory.current'] if (p:=cg/d/n).exists()}}
wsl_config=configparser.ConfigParser();wsl_config.read('/etc/wsl.conf')
out['wsl_conf_selected']={s+'.'+k:wsl_config.get(s,k) for s,k in [('boot','systemd'),('time','useWindowsTimezone')]}
out['wsl_conf_sha256']=hashlib.sha256(Path('/etc/wsl.conf').read_bytes()).hexdigest()
out['sysctl_etc_declarations']=[str(p)+':'+str(i+1)+':'+line for p in list(Path('/etc/sysctl.d').glob('*.conf'))+[Path('/etc/sysctl.conf')] if p.is_file() for i,line in enumerate(p.read_text().splitlines()) if not line.lstrip().startswith('#') and re.search(r'^\s*vm[./]swappiness\s*=',line)]
targets=['/etc/systemd/system/user-1000.slice.d/60-native-stack-memory.conf','/etc/systemd/system/native-stack-non-systemd-memory.service','/etc/systemd/system/multi-user.target.wants/native-stack-non-systemd-memory.service','/etc/sysctl.d/90-native-stack-swappiness.conf']
out['new_targets']={t:('present' if Path(t).exists() or Path(t).is_symlink() else 'absent') for t in targets}
ps=r"""
$ErrorActionPreference='Stop'
$configPath=Join-Path $env:USERPROFILE '.wslconfig'
$bytes=[IO.File]::ReadAllBytes($configPath)
$sha=[Security.Cryptography.SHA256]::Create()
$hash=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
$reader=[IO.StreamReader]::new([IO.MemoryStream]::new($bytes),$true)
$configText=$reader.ReadToEnd()
$reader.Dispose()
$profileLeaf=Split-Path $env:USERPROFILE -Leaf
$configText=[regex]::Replace($configText,[regex]::Escape($profileLeaf),'<PROFILE>',[Text.RegularExpressions.RegexOptions]::IgnoreCase)
$configText=[regex]::Replace($configText,'(?i)([A-Z]:\\+Users\\+)[^\\\r\n]+','$1<PROFILE>')
$active=@();foreach($line in ($configText -split '\r?\n')) {if($line -match '^\s*(\[|[^#;\s][^=]*=)'){$active+=$line.Trim()}}
$cs=Get-CimInstance Win32_ComputerSystem
$os=Get-CimInstance Win32_OperatingSystem
$mem=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$chrome=@(Get-Process chrome -ErrorAction SilentlyContinue)
$chromePerf=@(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -Filter "Name LIKE 'chrome%'")
$vmmem=@(Get-Process vmmemWSL -ErrorAction SilentlyContinue)
[ordered]@{path='C:\Users\<PROFILE>\.wslconfig';file_sha256=$hash;active_ini=$active;total_physical_bytes=[uint64]$cs.TotalPhysicalMemory;total_visible_kib=[uint64]$os.TotalVisibleMemorySize;available_bytes=[uint64]$mem.AvailableBytes;committed_bytes=[uint64]$mem.CommittedBytes;commit_limit_bytes=[uint64]$mem.CommitLimit;chrome_process_count=$chrome.Count;chrome_working_set_sum_bytes=[uint64](($chrome|Measure-Object WorkingSet64 -Sum).Sum);chrome_private_commit_sum_bytes=[uint64](($chrome|Measure-Object PrivateMemorySize64 -Sum).Sum);chrome_perf_instances=$chromePerf.Count;chrome_private_working_set_sum_bytes=[uint64](($chromePerf|Measure-Object WorkingSetPrivate -Sum).Sum);vmmemWSL_process_count=$vmmem.Count;vmmemWSL_working_set_sum_bytes=[uint64](($vmmem|Measure-Object WorkingSet64 -Sum).Sum)}|ConvertTo-Json -Depth 5 -Compress
"""
win=timed(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',ps])
win['command']=['powershell.exe','-NoProfile','-NonInteractive','-Command','read-only CIM/Get-Process and masked .wslconfig capture (capture_memory_readonly.py)']
win['data']=json.loads(win.pop('stdout')) if win['exit_code']==0 else {}
out['windows']=win
print('DATA='+json.dumps(out))
