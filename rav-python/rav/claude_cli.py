"""Talking to Claude through Claude Code (the `claude` command), which signs in with the
user's own Claude account — no API key and no extra payment beyond the account.

Every request is one `claude -p` run: the prompt goes in on stdin (no limit on its length),
the answer comes back as JSON."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from .log import log


class ClaudeError(RuntimeError):
    pass


def find_claude():
    """The path of the claude command, or None."""
    p = shutil.which("claude")
    if p:
        return p
    home = os.path.expanduser("~")
    for c in (os.path.join(home, ".local", "bin", "claude.exe"),
              os.path.join(home, ".local", "bin", "claude"),
              os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "claude", "claude.exe"),
              "/usr/local/bin/claude", "/opt/homebrew/bin/claude"):
        if c and os.path.isfile(c):
            return c
    return None


# ---------- a connection key (claude setup-token), for computers where the login is not kept ----------
def _key_file():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "rav", "claude-key.txt")


def saved_key():
    try:
        with open(_key_file(), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def save_key(key):
    key = re.sub(r"\s+", "", key or "")
    p = _key_file()
    if not key:
        if os.path.isfile(p):
            os.remove(p)
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(key)


def _env():
    env = dict(os.environ)
    key = saved_key()
    if key:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = key
    return env


def open_setup_token_window():
    """A console window running `claude setup-token`: the user signs in and gets the key there."""
    exe = find_claude()
    if not exe:
        raise ClaudeError("לא נמצא Claude Code (הפקודה claude). ראו README — התקנה.")
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/k", exe, "setup-token"], creationflags=0x00000010)  # CREATE_NEW_CONSOLE
    else:
        subprocess.Popen([exe, "setup-token"])


def _command(exe):
    if exe.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", exe]
    return [exe]


def status():
    """(ok, message): whether claude is installed and signed in."""
    exe = find_claude()
    if not exe:
        return False, ("לא נמצא Claude Code במחשב. מתקינים אותו פעם אחת (ראו README), "
                       "מריצים בחלון פקודה את הפקודה claude ומתחברים עם חשבון Claude.")
    try:
        out = ask("ענה רק במילה: מוכן", tools=(), timeout=180)
    except ClaudeError as e:
        return False, str(e)
    log("claude מחובר")
    return True, f"Claude מחובר ({out.strip()[:20]})"


def ask(prompt, tools=(), cwd=None, model=None, timeout=1800, system=None):
    """Claude's answer (text) to prompt. tools: the built-in tools it may use, e.g.
    ("WebSearch", "WebFetch"); none by default."""
    exe = find_claude()
    if not exe:
        raise ClaudeError("לא נמצא Claude Code (הפקודה claude). ראו README — התקנה.")
    cmd = _command(exe) + ["-p", "--output-format", "json", "--no-session-persistence",
                           "--tools", ",".join(tools) if tools else ""]
    if tools:
        cmd += ["--allowedTools", ",".join(tools)]
    if model:
        cmd += ["--model", model]
    if system and not tools:
        # no tools: our own short instructions in place of Claude Code's long ones (fewer tokens)
        cmd += ["--system-prompt", system]
    elif system:
        cmd += ["--append-system-prompt", system]
    if cwd is None:     # a neutral folder: no project instructions of another folder get in
        cwd = os.path.join(tempfile.gettempdir(), "rav-claude")
        os.makedirs(cwd, exist_ok=True)
    flags = 0x08000000 if sys.platform == "win32" else 0   # CREATE_NO_WINDOW
    log(f"claude ← {len(prompt)} תווים, כלים: {','.join(tools) or '-'}")
    try:
        r = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, cwd=cwd,
                           timeout=timeout, creationflags=flags, env=_env())
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"Claude לא ענה תוך {timeout // 60} דקות")
    out = r.stdout.decode("utf-8", "replace").strip()
    err = r.stderr.decode("utf-8", "replace").strip()
    data = None
    try:
        data = json.loads(out)
    except ValueError:
        # sometimes there are lines before the JSON
        m = re.search(r"\{.*\}\s*$", out, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except ValueError:
                pass
    if not isinstance(data, dict):
        msg = (err or out or f"קוד יציאה {r.returncode}")[-800:]
        log(f"claude ✗ {msg}")
        raise ClaudeError(_explain(msg))
    if data.get("is_error") or data.get("subtype", "success") != "success":
        msg = str(data.get("result") or data.get("subtype") or err)[-800:]
        log(f"claude ✗ {msg}")
        raise ClaudeError(_explain(msg))
    text = data.get("result") or ""
    log(f"claude → {len(text)} תווים")
    return text


def _explain(msg):
    low = msg.lower()
    if "login" in low or "log in" in low or "authenticat" in low or "api key" in low:
        return ("Claude Code לא מחובר לחשבון. לחצו בסרגל העליון על 'חיבור ל־Claude…' ועקבו אחרי "
                "ההוראות שם (מקבלים מפתח חיבור פעם אחת).\n\n" + msg)
    if "limit" in low or "usage" in low or "quota" in low:
        return ("הגעתם למגבלת השימוש של חשבון Claude לעכשיו. חכו עד שהמגבלה תתאפס ולחצו שוב — "
                "העבודה שכבר נעשתה שמורה והתוכנה תמשיך מאותו מקום.\n\n" + msg)
    return "Claude החזיר שגיאה:\n" + msg


def json_from(text):
    """The JSON value in Claude's answer (in a ```json block or bare)."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    cands = [m.group(1)] if m else []
    cands.append(text)
    for c in cands:
        c = c.strip()
        for opener, closer in (("{", "}"), ("[", "]")):
            i, j = c.find(opener), c.rfind(closer)
            if i != -1 and j > i:
                try:
                    return json.loads(c[i:j + 1])
                except ValueError:
                    continue
    raise ClaudeError("לא הצלחתי לקרוא את התשובה של Claude (ציפיתי ל־JSON):\n" + text[:600])
