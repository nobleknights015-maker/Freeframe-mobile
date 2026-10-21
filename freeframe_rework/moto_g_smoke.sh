#!/bin/sh
set -eu

APK="sim-apk/FreeFrame-Rework-Test.apk"
adb install -r "$APK"
PACKAGE=$(adb shell pm list packages | sed -n 's/^package://p' | grep -Ei 'freeframe|local.diffusion|local_diffusion' | head -n 1 || true)
if [ -z "$PACKAGE" ]; then
  echo 'Could not determine installed FreeFrame package name.'
  adb shell pm list packages
  exit 1
fi
echo "Testing package: $PACKAGE"

ACTIVITY=$(adb shell cmd package resolve-activity --brief -c android.intent.category.LAUNCHER "$PACKAGE" 2>/dev/null | tr -d '\r' | tail -n 1)
if [ -z "$ACTIVITY" ] || ! echo "$ACTIVITY" | grep -q '/'; then
  echo 'Could not resolve FreeFrame launcher activity.'
  adb shell dumpsys package "$PACKAGE" | grep -A 8 -B 2 -i 'MAIN' || true
  exit 1
fi
echo "Launching activity: $ACTIVITY"
adb logcat -c
adb shell am start -W -n "$ACTIVITY"
sleep 5

if ! adb shell pidof "$PACKAGE" >/dev/null; then
  echo 'FreeFrame process did not survive initial launch.'
  adb logcat -d -t 300 | grep -Ei "$PACKAGE|AndroidRuntime|FATAL EXCEPTION|flutter" || true
  exit 1
fi
FOCUS=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -n 2 || true)
echo "Initial focus: $FOCUS"
if ! echo "$FOCUS" | grep -q "$PACKAGE"; then
  echo 'FreeFrame did not remain in the foreground after launch.'
  adb logcat -d -t 300 | grep -Ei "$PACKAGE|AndroidRuntime|FATAL EXCEPTION|flutter" || true
  exit 1
fi

adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml window.xml >/dev/null

python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET

tree = ET.parse('window.xml')
nodes = list(tree.getroot().iter('node'))

def center(node):
    b = node.attrib.get('bounds', '')
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
    if not m:
        raise SystemExit(f'No bounds for node: {node.attrib}')
    x1,y1,x2,y2 = map(int, m.groups())
    return (x1+x2)//2, (y1+y2)//2

prompt = next((n for n in nodes if 'Describe what you want' in (n.attrib.get('text','') + n.attrib.get('content-desc',''))), None)
if prompt is None:
    prompt = next((n for n in nodes if n.attrib.get('class','').endswith('EditText')), None)
if prompt is not None:
    x,y = center(prompt)
else:
    size = subprocess.check_output(['adb','shell','wm','size'], text=True)
    m = re.search(r'(\d+)x(\d+)', size)
    if not m:
        raise SystemExit('Could not determine display size for prompt fallback')
    w,h = map(int, m.groups())
    # Stay above the gesture/navigation inset while targeting the composer.
    x,y = w//2, h-220
    print(f'Prompt semantics unavailable; using composer fallback at {x},{y}')
subprocess.run(['adb','shell','input','tap',str(x),str(y)], check=True)
PY

sleep 2
adb shell dumpsys input_method > input_method.txt
if ! grep -Eq 'mInputShown=true|isInputViewShown=true|mShowRequested=true' input_method.txt; then
  echo 'Keyboard did not become visible after tapping prompt field.'
  adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' || true
  exit 1
fi

adb shell input text 'FreeFrameKeyboardTest'
sleep 1
if ! adb shell pidof "$PACKAGE" >/dev/null; then
  echo 'FreeFrame process died while typing into the prompt.'
  exit 1
fi

adb shell input keyevent 4
sleep 1
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml window.xml >/dev/null

python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET

tree = ET.parse('window.xml')
nodes = list(tree.getroot().iter('node'))
attach = next((n for n in nodes if 'Attach reference' in (n.attrib.get('content-desc','') + n.attrib.get('text',''))), None)
if attach is not None:
    b = attach.attrib['bounds']
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
    x1,y1,x2,y2 = map(int, m.groups())
    x,y = (x1+x2)//2, (y1+y2)//2
else:
    size = subprocess.check_output(['adb','shell','wm','size'], text=True)
    m = re.search(r'(\d+)x(\d+)', size)
    if not m:
        raise SystemExit('Could not determine display size for attach fallback')
    w,h = map(int, m.groups())
    x,y = 55, h-220
    print(f'Attach semantics unavailable; using composer fallback at {x},{y}')
subprocess.run(['adb','shell','input','tap',str(x),str(y)], check=True)
PY

sleep 2
FOCUS=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -n 1 || true)
echo "Picker focus: $FOCUS"
if echo "$FOCUS" | grep -q "$PACKAGE"; then
  echo 'Reference picker did not leave FreeFrame.'
  exit 1
fi

adb shell input keyevent 4
sleep 1
adb shell am send-trim-memory "$PACKAGE" RUNNING_LOW || true
adb shell am send-trim-memory "$PACKAGE" MODERATE || true
sleep 1

SIZE=$(adb shell wm size)
HEIGHT=$(echo "$SIZE" | sed -n 's/.* \([0-9][0-9]*\)x\([0-9][0-9]*\).*/\2/p')
if [ -z "$HEIGHT" ]; then
  echo 'Could not determine display size after memory trim.'
  exit 1
fi
adb shell input tap 55 $((HEIGHT - 220))
sleep 2

if ! adb shell pidof "$PACKAGE" >/dev/null; then
  echo 'FreeFrame process died after low-memory picker test.'
  exit 1
fi
FOCUS=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -n 1 || true)
echo "Low-memory picker focus: $FOCUS"
if echo "$FOCUS" | grep -q "$PACKAGE"; then
  echo 'Reference picker did not reopen after memory trim.'
  exit 1
fi

echo 'Moto G class smoke test passed.'
