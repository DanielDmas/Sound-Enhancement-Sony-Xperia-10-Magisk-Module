#!/usr/bin/env python3
"""Command boundary fake. Test the real shell code without an Android device."""
import json, os, pathlib, sys, time
root=pathlib.Path(os.environ['FAKE_ANDROID_ROOT'])
state=json.loads((root/'android.json').read_text())
name=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:]
# AOSP's am shell wrapper delegates these commands to cmd activity.
if name=='cmd' and args[:1]==['activity']:
 name='am';args=args[1:]
with (root/'calls.jsonl').open('a') as out:out.write(json.dumps([name,*args])+'\n')
def finish(text='',code=0):
 print(text);sys.exit(code)
if name=='id':finish('0' if state.get('root',True) else '10001')
if name=='am':
 if args==['get-current-user']:finish(str(state.get('user',0)))
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
  if state.get('dump_hang'):time.sleep(12)
  if state.get('dump_fail'):finish('Audio service unavailable',1)
  finish(state.get('audio','PlaybackActivityMonitor dump time: test\n  players:\n'))
 if args and args[0]=='package':finish('Sony package fixture')
 if args==['media.audio_flinger']:finish('AudioFlinger fixture: no physical processing measurement')
 if args==['media_session']:finish('No media-session notification is required for audio ownership.')
if name=='cmd':
 if state.get('packages_fail'):finish('Error reading packages',1)
 finish(state.get('packages',''))
if name=='ps':
 if state.get('ps_fail'):finish('',1)
 finish(state.get('processes','PID NAME\n'))
if name=='pidof':
 value=state.get('pids',{}).get(args[0],'')
 finish(value,0 if value else 1)
if name=='getenforce':finish('Enforcing')
if name=='getprop':finish({'ro.product.device':'lilac','ro.build.version.sdk':'32','sys.boot_completed':'1'}.get(args[0],''))
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
