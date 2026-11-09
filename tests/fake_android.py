#!/usr/bin/env python3
"""Command boundary fake. Test the real shell code without an Android device."""
import json, os, pathlib, stat, subprocess, sys, time
root=pathlib.Path(os.environ['FAKE_ANDROID_ROOT'])
state=json.loads((root/'android.json').read_text())
name=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:]
if state.get('record_fds'):
 fds={}
 for fd in [0,1,2,3,7,8,9]:
  try:fds[str(fd)]=stat.S_IFMT(os.fstat(fd).st_mode)
  except OSError:fds[str(fd)]=None
 with (root/'fds.jsonl').open('a') as out:out.write(json.dumps([name,fds])+'\n')
# Binder passes these descriptors to system_server. Model its inability to use
# root-private regular files (the old fake incorrectly accepted every FD type).
if name in ['cmd','am','pm','appops'] and state.get('strict_binder_fds',True):
 for fd in [0,1,2]:
  if stat.S_ISREG(os.fstat(fd).st_mode):
   print('cmd: Failure calling service: Failed transaction (private file descriptor)',file=sys.stderr)
   sys.exit(1)
# AOSP's am shell wrapper delegates these commands to cmd activity.
if name=='cmd' and args[:1]==['activity']:
 name='am';args=args[1:]
with (root/'calls.jsonl').open('a') as out:out.write(json.dumps([name,*args])+'\n')
def finish(text='',code=0):
 print(text);sys.exit(code)
if name=='id':finish('0' if state.get('root',True) else '10001')
if name=='am':
 if args==['get-current-user']:
  if state.get('user_stderr'):print(state['user_stderr'],file=sys.stderr)
  finish(str(state.get('user_output',state.get('user',0))),state.get('user_exit',0))
 if args and args[0]=='broadcast':
  time.sleep(state.get('am_delay',0))
  if state.get('close_fail') and 'android.media.action.CLOSE_AUDIO_EFFECT_CONTROL_SESSION' in args:finish('Error: CLOSE rejected',1)
  if state.get('am_fail'):finish('Error: java.lang.SecurityException: Permission Denial',state.get('am_exit',0))
  if state.get('am_unconfirmed'):finish('Broadcasting: Intent only')
  finish('Broadcasting: Intent\nBroadcast completed: result=0')
 if args and args[0]=='start-activity':
  if state.get('panel_fail'):finish('Error: Activity class does not exist.',0)
  finish('Starting: Intent')
 finish('Error: unsupported AM command',1)
if name=='dumpsys':
 if args==['audio']:
  if state.get('dump_orphan_fds'):
   subprocess.Popen([sys.executable,'-c','import time; time.sleep(12)'],start_new_session=True)
  if state.get('dump_hang'):time.sleep(12)
  if state.get('dump_fail'):finish('Audio service unavailable',1)
  finish(state.get('audio','PlaybackActivityMonitor dump time: test\n  players:\n'))
 if args and args[0]=='package':finish('Sony package fixture')
 if args==['media.audio_flinger']:finish('AudioFlinger fixture: no physical processing measurement')
 if args==['media_session']:finish('No media-session notification is required for audio ownership.')
if name=='cmd':
 if args==['package','query-activities','--brief','-a','android.media.action.DISPLAY_AUDIO_EFFECT_CONTROL_PANEL']:
  finish('com.sonyericsson.soundenhancement/.SoundEnhancementRedirector')
 if args!=['package','list','packages','-U','--user',str(state.get('user',0))]:
  finish('Error: unsupported package command '+repr(args),1)
 if state.get('packages_stderr'):print(state['packages_stderr'],file=sys.stderr)
 if state.get('packages_fail'):
  finish(state.get('packages_partial','Error reading packages'),state.get('packages_exit',1))
 finish(state.get('packages',''))
if name=='ps':
 if state.get('ps_fail'):finish('',1)
 finish(state.get('processes','PID NAME\n'))
if name=='pidof':
 value=state.get('pids',{}).get(args[0],'')
 finish(value,0 if value else 1)
if name=='getenforce':finish('Enforcing')
if name=='getprop':finish(state.get('props',{}).get(args[0],{'ro.product.device':'lilac','ro.product.model':'G8441','ro.build.version.sdk':'32','sys.boot_completed':'1'}.get(args[0],'')))
if name=='appops':finish('RECORD_AUDIO: allow')
if name=='logcat':finish('Diagnostic log fixture')
if name in ['resetprop','killall']:finish('')
if name=='pm':finish('Permission denied' if state.get('pm_fail') else '',1 if state.get('pm_fail') else 0)
if name=='nohup':finish('Watcher launch captured by test fake')
if name=='sleep':
 counter=root/'sleeps'
 n=int(counter.read_text())+1 if counter.exists() else 1
 counter.write_text(str(n))
 if state.get('stop_after') and n>=state['stop_after']:
  pathlib.Path(os.environ['SEFX_STATE_DIR'],'config').write_text('auto=0\n')
 time.sleep(0.05)
 finish('')
finish('Unsupported fake command: '+name,1)
