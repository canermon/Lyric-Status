""" Copyright: canermon 2026
 Created by https://github.com/canermon
 Do NOT Republish, Re Distribute, Or Claim as your own"""

import platform, subprocess, time, re, sys, requests, os
import syncedlyrics

OS = platform.system()

# terminal display 

def clear():
    os.system("cls" if OS == "Windows" else "clear")

def draw(status, song, artist, line_index, line_total, lyric):
    clear()
    w = 52
    bar = "─" * w
    def row(label, value):
        print(f"  {label:<8} {value}")

    print(f"\n  {bar}")
    print(f"  {'lyric status':^{w}}")
    print(f"  {bar}")
    dot = "● active" if status == "active" else "○ play sum on spotify dumass"
    row("status :", dot)
    if song:
        row("song   :", f"{song} — {artist}")
        row("line   :", f"{line_index} / {line_total}")
        row("lyric  :", lyric if lyric else "—")
    print(f"  {bar}\n")

# spotify readers 

def get_spotify_macos():
    script = '''
    tell application "Spotify"
        if player state is playing then
            return (name of current track) & "|" & (artist of current track) & "|" & (player position as string)
        end if
    end tell
    '''
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
        parts = r.stdout.strip().split("|")
        if len(parts) >= 3:
            return parts[0], parts[1], int(float(parts[2]) * 1000)
    except Exception:
        pass
    return None

def get_spotify_linux():
    def dbus(prop):
        return subprocess.run([
            "dbus-send", "--print-reply",
            "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player",
            f"string:{prop}"
        ], capture_output=True, text=True, timeout=3)
    try:
        pos_r  = dbus("Position")
        meta_r = dbus("Metadata")
        pos_m  = re.search(r'int64\s+(\d+)', pos_r.stdout)
        title_m  = re.search(r'xesam:title[^\n]*\n\s+variant\s+string\s+"([^"]+)"', meta_r.stdout)
        artist_m = re.search(r'xesam:artist[^\n]*\n.*?string\s+"([^"]+)"', meta_r.stdout, re.DOTALL)
        pos_us = int(pos_m.group(1)) if pos_m else 0
        title  = title_m.group(1)  if title_m  else None
        artist = artist_m.group(1) if artist_m else ""
        if not title: return None
        return title, artist, pos_us // 1000
    except Exception:
        pass
    return None

_win_start, _win_key = 0.0, ""
def get_spotify_windows():
    global _win_start, _win_key
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-Process spotify -ErrorAction SilentlyContinue | "
             "Where-Object {$_.MainWindowTitle -ne ''} | "
             "Select-Object -ExpandProperty MainWindowTitle"],
            capture_output=True, text=True, timeout=3
        )
        title = r.stdout.strip()
        if not title or " - " not in title or title.lower().startswith("spotify"):
            return None
        artist, track = title.split(" - ", 1)
        key = f"{artist}|{track}"
        if key != _win_key:
            _win_key = key
            _win_start = time.time()
        return track.strip(), artist.strip(), int((time.time() - _win_start) * 1000)
    except Exception:
        pass
    return None

def get_spotify_info():
    if OS == "Darwin":  return get_spotify_macos()
    if OS == "Linux":   return get_spotify_linux()
    if OS == "Windows": return get_spotify_windows()
    print(f"unsupported OS: {OS}"); sys.exit(1)

#discord

DISCORD_TOKEN = ""

def set_discord_status(text):
    r = requests.patch(
        "https://discord.com/api/v9/users/@me/settings",
        headers={"Authorization": DISCORD_TOKEN, "Content-Type": "application/json"},
        json={"custom_status": {
            "text":       text[:128] if text else None,
            "emoji_name": "🎵"      if text else None,
        }}
    )
    if r.status_code == 401:
        clear()
        print("\ndiscord token invalid or expired\n")
        sys.exit(1)
    return r.status_code

#lyrics 

def parse_lrc(lrc_text):
    lines, pattern = [], re.compile(r'\[(\d+):(\d+)[.:](\d+)\](.*)')
    for line in lrc_text.split('\n'):
        m = pattern.match(line.strip())
        if m:
            mins, secs, frac, text = m.groups()
            ms = (int(mins)*60 + int(secs))*1000 + int(frac)*(10 if len(frac)==2 else 1)
            if text.strip():
                lines.append((ms, text.strip()))
    return sorted(lines, key=lambda x: x[0])

def current_lyric_index(lines, pos_ms):
    idx = 0
    for i, (ts, _) in enumerate(lines):
        if ts <= pos_ms: idx = i
        else: break
    return idx

# main 

def main():
    global DISCORD_TOKEN

    clear()
    print("\nLyric Status\n")
    print()
    DISCORD_TOKEN = input("paste discord token here:").strip()

    if not DISCORD_TOKEN:
        print("  no token entered dumass"); sys.exit(1)

    # verify token
    r = requests.get("https://discord.com/api/v9/users/@me",
                     headers={"Authorization": DISCORD_TOKEN})
    if r.status_code == 401:
        print("\n invalid token:(:(\n"); sys.exit(1)

    username = r.json().get("username", "unknown")

    track_key, lyrics, last, last_idx = "", [], "", -1

    try:
        while True:
            info = get_spotify_info()

            if not info:
                if last:
                    set_discord_status(None)
                    last, last_idx = "", -1
                draw("waiting", None, None, 0, 0, None)
                time.sleep(5)
                continue

            track, artist, pos_ms = info
            key = f"{artist}|{track}"

            if key != track_key:
                track_key, last, last_idx = key, "", -1
                lrc = syncedlyrics.search(f"{track} {artist}")
                lyrics = parse_lrc(lrc) if lrc else []

            idx   = current_lyric_index(lyrics, pos_ms) if lyrics else 0
            lyric = lyrics[idx][1] if lyrics else "no synced lyrics"

            if lyric != last or idx != last_idx:
                last, last_idx = lyric, idx
                if lyrics:
                    set_discord_status(lyric)

            draw("active", track, artist, idx + 1 if lyrics else 0, len(lyrics), lyric)
            time.sleep(1)

    except KeyboardInterrupt:
        clear()
        print("\n  stopping ")
        set_discord_status(None)
        print("  done\n")

if __name__ == "__main__":
    main()
