# AEGIS Computer Control Subsystem

**Engine Implementation:** `backend/computer_control.py`  
**Display Server:** Wayland (`wayland-1`) / X11 (`:0`)  
**Input Automation:** `/usr/bin/wtype` (Wayland keystroke simulator)  
**Clipboard Automation:** `/usr/bin/wl-copy`, `/usr/bin/wl-paste`  

---

## 1. Computer Control Capabilities

1. **Keystroke Simulation (`wtype`):**
   - Inject text into active focused windows with exact character precision.
   - Support special keys: Return, Tab, Escape, Backspace, Arrow navigation.
2. **System Clipboard Synchronization (`wl-copy` / `wl-paste`):**
   - Read and write to the Wayland system clipboard seamlessly.
3. **Application Control:**
   - Launch authorized desktop tools and applications via non-blocking subprocess sessions.

---

## 2. Permission Gating & Risk Matrix

- **Low Risk:** Reading clipboard, simulating non-destructive keys (Tab, Arrows).
- **Medium Risk:** Typing text into active windows, copying text to clipboard, launching standard tools.
- **High Risk:** Injecting shell commands with `sudo`, modifying system partitions, financial actions.
- **Enforcement:** High-risk actions require explicit interactive user authorization.
