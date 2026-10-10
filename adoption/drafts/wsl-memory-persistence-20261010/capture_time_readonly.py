#!/usr/bin/env python3
"""Read only the CC-designated time inputs; print command receipts to stdout."""
import subprocess,json,os,hashlib
from pathlib import Path
def timed(cmd,env=None):
 a=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
 p=subprocess.run(cmd,capture_output=True,text=True,env=env)
 b=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
 return {'command':cmd,'start_utc':a,'end_utc':b,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
env=os.environ.copy();env['XDG_RUNTIME_DIR']='/run/user/1000'
out={'evidence_class':'native_proven','mutations':[],'commands':[timed(['chronyc','tracking']),timed(['chronyc','sources']),timed(['chronyd','--version']),timed(['timedatectl','show']),timed(['systemctl','--user','list-timers','--all','--no-pager'],env)]}
out['commands'][-1]['environment_override']={'XDG_RUNTIME_DIR':'/run/user/1000'}
out['timer_files']=[]
r=Path.home()/'.config/systemd/user'
for p in sorted(r.glob('*.timer')):
 s=p.read_text()
 if any(l.startswith('OnCalendar=') and not(l.endswith(' UTC') or l.endswith(' America/New_York')) for l in s.splitlines()):
  target=r/(p.name+'.d')/'90-native-stack-explicit-zone.conf'
  out['timer_files'].append({'file':'~/.config/systemd/user/'+p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text':s,'draft_target':'~/.config/systemd/user/'+p.name+'.d/90-native-stack-explicit-zone.conf','draft_target_precondition':'present' if target.exists() or target.is_symlink() else 'absent'})
out['chrony_config_selected']=[]
for p in [Path('/etc/chrony/chrony.conf'),*sorted(Path('/etc/chrony/sources.d').glob('*.sources')),*sorted(Path('/etc/chrony/conf.d').glob('*.conf'))]:
 if p.is_file():
  out['chrony_config_selected'] += [{'file':str(p),'line':i+1,'text':l.strip()} for i,l in enumerate(p.read_text().splitlines()) if l.lstrip().startswith('refclock ')]
print('DATA='+json.dumps(out,separators=(',',':')))
