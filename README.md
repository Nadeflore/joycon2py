# joycon2py

A lightweight Python script that turns the Joy-Con 2's and the Pro Controller 2 into working PC Controllers.

---

## DISCLAIMER

This project is **Windows-only**, primarily because `vgamepad` (used for virtual controller output) is exclusive to Windows.  
You're free to make your own macOS/Linux fork if you want.

Supported controllers:
Joy-Con 2: Full support,
Pro Controller 2: Full support,
NSO GC Controller: Semi support (Joysticks confirmed to work, buttons may not be mapped/mapped correctly in code yet, requires data sent over by someone with one)

If the program crashes, it means it couldn't connect to your joycon. Often caused by constantly disconnecting and connecting them, so let them cool down for a bit.
---

## DEPENDENCIES

- Python (3.7+)
- [`bleak`](https://github.com/hbldh/bleak)  
  → `pip install bleak`  
- [`vgamepad`](https://github.com/yannbouteiller/vgamepad)  
  → `pip install vgamepad`  
  → Requires [ViGEmBus drivers](https://github.com/ViGEm/ViGEmBus/releases/latest) installed

---

## How do I use it?
- Download the whole repo (green button titled code, press download zip. you can delete readme.md if you want)
- Open the main.py script (dont open solo/duo/pro_logic.py those are modules)
- Pick your amount of players
- Pick everyone's controller
- If using a singular joycon you'll be asked if its Left or Right
- If using dual joycons itll ask you to pair one joycon then the other
- If using a pro controller it just asks you to pair it
- When its all done, you'll have SDL controllers ready for every player to use.

> 💡 Note: Bit layouts differ slightly between left and right Joy-Cons, so correct side pairing is important.

---

## RESEARCH

Here, I'll document some findings on Joy-Con 2 behavior (if anyone is interested)

Something I've documented just in general is something I call BLE DEADMODE. It's where if you keep constantly trying to use the program/connect the joycons a ton, the joycons eventually can't connect unless you let them idle for a bit. This is probably because the bluetooth stuff has to cool down sometimes. So, make sure you're not trying to use the program like twice per second or something

### 🔔 Notifications

**Example notification:**

35ae0000000000e0ff0ffff77f20e8790000000000000000000000000000005d0e000000000000000001000000000000000000000000000000000000000000


**Breakdown:**

- `35` – Header  
- `ae00` – Timestamp (seems to increment every ~minute)  
- `00000000` – Button inputs  
- `e0ff0ffff77f` – Unknown (possibly battery or sensor flags?)  
- `20e879` – Stick data  
- `0000000000000000000000000000005d0e000000000000000001000000000000000000000000000000000000000000` – Unknown (possibly IMU/battery?)  

> ⚠️ Haven't found gyro, accel, or battery data yet.  
> Writing a **LED command works**, but it causes notifications to stop.  
> Possibly because the Joy-Con expects a strict command protocol and "crashes" if something's missing or invalid.  
> We'll need to reverse this format further to find valid LED and IMU enable subcommands.
> IMU data seems to be the zeroed out bytes, possibly enabled by commands, which we have yet to figure out.

---

## Can I edit the code?

Absolutely!  
Make any changes you like, or submit a pull request if you think it's worth sharing.

---
