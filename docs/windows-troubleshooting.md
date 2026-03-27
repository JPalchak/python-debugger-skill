# Windows Troubleshooting

This document covers common issues when running the Python Debugger on Windows.

---

## Firewall / Loopback Connections Blocked

**Symptom:** `cmd_start` times out with "Debugger server did not start in time".

**Cause:** Some Windows security tools block TCP connections to `127.0.0.1`
even from the same machine.

**Fix:** Allow Python (or the specific port range) in your Windows Firewall or
security software.  The debugger uses a random unprivileged port each session;
no persistent firewall rule is needed if loopback traffic is generally allowed.

---

## `python` vs `python3`

**Symptom:** `python3: command not found` or similar error.

**Cause:** On Windows the launcher is typically `python`, not `python3`.

**Fix:** Replace `python3` with `python` in all commands, or create an alias:
```powershell
Set-Alias python3 python
```

---

## Antivirus Interference

**Symptom:** Subprocess fails to start; session file is never created.

**Cause:** Some antivirus products quarantine or block newly spawned Python
subprocesses.

**Fix:** Add your Python executable and the repository folder to the antivirus
exclusion list.

---

## `SIGTERM` Cannot Terminate the Server

**Symptom:** Sending SIGTERM from an external tool does not stop the debugger
server.

**Cause:** `SIGTERM` is not reliably delivered on Windows.

**Fix:** Use the `quit` command instead:
```bash
python debugger.py quit
```
Or press `Ctrl+C` in the terminal running the server (SIGINT is supported).

---

## Session Files Not Cleaned Up

**Symptom:** Old session files accumulate in `%USERPROFILE%\.claude_debugger\`.

**Cause:** If the server process is force-killed (e.g. Task Manager), it cannot
clean up its session file.

**Fix:** Delete stale JSON files manually:
```powershell
Remove-Item "$env:USERPROFILE\.claude_debugger\debug_*.json"
```
The debugger will also automatically remove stale sessions when it detects the
corresponding process is no longer running.

---

## Port Already in Use

**Symptom:** `ConnectionRefusedError` or similar socket error.

**Cause:** Unlikely with OS-assigned random ports, but can happen if a previous
session was not cleaned up and the same port was re-assigned.

**Fix:** Run `python debugger.py quit` to clean up, then restart.

---

## Running Under PowerShell

The debugger is invoked the same way in PowerShell as in CMD:
```powershell
python scripts\debugger.py start my_script.py
python scripts\debugger.py break -f my_script.py -l 10
python scripts\debugger.py continue
```

---

## Known Limitations on Windows

| Feature | Status |
|---|---|
| Launch-mode debugging | ✅ Supported |
| TCP loopback IPC | ✅ Supported |
| Eval timeout (threading) | ✅ Supported |
| `SIGTERM` graceful shutdown | ⚠️ Not delivered externally; use `quit` command |
| Attach to existing process | 🚧 Not yet implemented |
