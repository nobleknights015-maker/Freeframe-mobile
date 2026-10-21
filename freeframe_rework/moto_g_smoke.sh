#!/bin/sh
set -eu

APK="sim-apk/FreeFrame-Rework-Test.apk"
adb install -r "$APK"
PACKAGE=$(adb shell pm list packages | sed -n 's/^package://p' | grep -Ei 'freeframe|local.diffusion|local_diffusion' | head -n 1 || true)
if [ -z "$PACKAGE" ]; then
  PACKAGE=$(unzip -p "$APK" META-INF/MANIFEST.MF 2>/dev/null | sed -n 's/^Package: //p' | head -n 1 || true)
fi
if [ -z "$PACKAGE" ]; then
  echo 'Could not determine installed FreeFrame package name.'
  adb shell pm list packages
  exit 1
fi
echo "Testing package: $PACKAGE"

adb shell monkey -p "$PACKAGE" -c android.intent.category.LAUNCHER 1 >/dev/null
sleep 4
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

prompt = next((n for n in nodes if 'Describe what you want' in n.attrib.get('text','')), None)
if prompt is None:
    prompt = next((n for n in nodes if n.attrib.get('class','').endswith('EditText')), None)
if prompt is None:
    raise SystemExit('Prompt field not found in Android UI hierarchy')
x,y = center(prompt)
subprocess.run(['adb','shell','input','tap',str(x),str(y)], check=True)
PY

sleep 2
adb shell dumpsys input_method > input_method.txt
if ! grep -Eq 'mInputShown=true|isInputViewShown=true|mShowRequested=true' input_method.txt; then
  echo 'Keyboard did not become visible after tapping prompt field.'
  cat input_method.txt
  exit 1
fi

adb shell input text 'FreeFrameKeyboardTest'
sleep 1
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml window.xml >/dev/null
grep -q 'FreeFrameKeyboardTest' window.xml || {
  echo 'Typed text was not retained in the prompt field.'
  exit 1
}

adb shell input keyevent 4
sleep 1
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml window.xml >/dev/null

python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET

tree = ET.parse('window.xml')
nodes = list(tree.getroot().iter('node'))
attach = next((n for n in nodes if n.attrib.get('content-desc') == 'Attach reference'), None)
if attach is None:
    raise SystemExit('Attach reference button not found')
b = attach.attrib['bounds']
m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
x1,y1,x2,y2 = map(int, m.groups())
subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)], check=True)
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

adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml window.xml >/dev/null
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET

tree = ET.parse('window.xml')
nodes = list(tree.getroot().iter('node'))
attach = next((n for n in nodes if n.attrib.get('content-desc') == 'Attach reference'), None)
if attach is None:
    raise SystemExit('Attach reference button disappeared after memory trim')
m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', attach.attrib['bounds'])
x1,y1,x2,y2 = map(int, m.groups())
subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)], check=True)
PY
sleep 2

if ! adb shell pidof "$PACKAGE" >/dev/null; then
  echo 'FreeFrame process died after low-memory picker test.'
  exit 1
fi

echo 'Moto G class smoke test passed.'
