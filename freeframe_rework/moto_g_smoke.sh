#!/bin/sh
set -eu

APK=$(find sim-apk -maxdepth 1 -type f -name 'FreeFrame-*.apk' | head -n 1)
if [ -z "$APK" ]; then echo 'Could not find downloaded FreeFrame APK.'; exit 1; fi
echo "Installing APK: $APK"
adb install -r "$APK"
PACKAGE=$(adb shell pm list packages | sed -n 's/^package://p' | grep -Ei 'freeframe|local.diffusion|local_diffusion' | head -n 1 || true)
if [ -z "$PACKAGE" ]; then echo 'Could not determine installed FreeFrame package name.'; exit 1; fi
echo "Testing package: $PACKAGE"
ACTIVITY=$(adb shell cmd package resolve-activity --brief -c android.intent.category.LAUNCHER "$PACKAGE" 2>/dev/null | tr -d '\r' | tail -n 1)
if [ -z "$ACTIVITY" ] || ! echo "$ACTIVITY" | grep -q '/'; then echo 'Could not resolve FreeFrame launcher activity.'; exit 1; fi
echo "Launching activity: $ACTIVITY"
adb logcat -c
adb shell am start -W -n "$ACTIVITY"
sleep 5
FOCUS=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -n 2 || true)
echo "Initial focus: $FOCUS"
if echo "$FOCUS" | grep -q 'com.android.settings'; then
  echo 'Android Settings permission screen detected; relaunching FreeFrame after permission handoff.'
  adb shell am force-stop com.android.settings || true
  adb shell am start -W -n "$ACTIVITY" >/dev/null
  sleep 4
  FOCUS=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -n 2 || true)
  echo "Post-settings focus: $FOCUS"
fi
if ! adb shell pidof "$PACKAGE" >/dev/null; then echo 'FreeFrame process did not survive initial launch.'; exit 1; fi
if ! echo "$FOCUS" | grep -q "$PACKAGE"; then echo 'FreeFrame did not remain in the foreground after permission handling.'; exit 1; fi

adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml window.xml >/dev/null
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
tree=ET.parse('window.xml'); nodes=list(tree.getroot().iter('node'))
def bounds(n):
 m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds','')); return tuple(map(int,m.groups())) if m else None
def center(n):
 x1,y1,x2,y2=bounds(n); return (x1+x2)//2,(y1+y2)//2
prompt=next((n for n in nodes if 'Describe what you want' in (n.attrib.get('text','')+n.attrib.get('content-desc',''))),None)
if prompt is None: prompt=next((n for n in nodes if n.attrib.get('class','').endswith('EditText')),None)
if prompt is not None: x,y=center(prompt)
else:
 s=subprocess.check_output(['adb','shell','wm','size'],text=True); m=re.search(r'(\d+)x(\d+)',s); w,h=map(int,m.groups()); x,y=w//2,h-220
subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
PY
sleep 2
adb shell dumpsys input_method > input_method.txt
if ! grep -Eq 'mInputShown=true|isInputViewShown=true|mShowRequested=true' input_method.txt; then echo 'Keyboard did not become visible after tapping prompt field.'; exit 1; fi
adb shell input text 'FreeFrameKeyboardTest'; sleep 1
if ! adb shell pidof "$PACKAGE" >/dev/null; then echo 'FreeFrame process died while typing.'; exit 1; fi
adb shell input keyevent 4; sleep 1

open_attach() {
  adb shell uiautomator dump /sdcard/window.xml >/dev/null
  adb pull /sdcard/window.xml window.xml >/dev/null
  python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
tree=ET.parse('window.xml'); nodes=list(tree.getroot().iter('node'))
def b(n):
 m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds','')); return tuple(map(int,m.groups())) if m else None
attach=next((n for n in nodes if 'Attach reference' in (n.attrib.get('content-desc','')+n.attrib.get('text',''))),None)
if attach is None:
 edit=next((n for n in nodes if n.attrib.get('class','').endswith('EditText')),None)
 eb=b(edit) if edit is not None else None
 candidates=[]
 if eb:
  ex1,ey1,ex2,ey2=eb
  for n in nodes:
   nb=b(n)
   if n.attrib.get('class','').endswith('Button') and nb:
    x1,y1,x2,y2=nb
    overlap=max(0,min(y2,ey2)-max(y1,ey1))
    if x2<=ex1+8 and overlap>0: candidates.append((ex1-x2,n))
 if candidates: attach=min(candidates,key=lambda z:z[0])[1]
if attach is None: raise SystemExit('Could not identify composer attach button')
x1,y1,x2,y2=b(attach); x,y=(x1+x2)//2,(y1+y2)//2
print('Attach tap:',x,y,attach.attrib)
subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
PY
}

adb logcat -c
open_attach
sleep 2
FOCUS=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -n 1 || true)
echo "Picker focus: $FOCUS"
if echo "$FOCUS" | grep -q "$PACKAGE"; then
  echo 'Reference picker did not leave FreeFrame. Picker diagnostics:'
  adb logcat -d -t 250 | grep -Ei "$PACKAGE|file_picker|ActivityTaskManager|ActivityManager|DocumentsUI|ACTION_OPEN_DOCUMENT|PlatformException|flutter" || true
  exit 1
fi
adb shell input keyevent 4; sleep 1
adb shell am send-trim-memory "$PACKAGE" RUNNING_LOW || true
adb shell am send-trim-memory "$PACKAGE" MODERATE || true
sleep 1
open_attach
sleep 2
if ! adb shell pidof "$PACKAGE" >/dev/null; then echo 'FreeFrame process died after low-memory picker test.'; exit 1; fi
FOCUS=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -n 1 || true)
echo "Low-memory picker focus: $FOCUS"
if echo "$FOCUS" | grep -q "$PACKAGE"; then echo 'Reference picker did not reopen after memory trim.'; exit 1; fi
echo 'Moto G class smoke test passed.'
