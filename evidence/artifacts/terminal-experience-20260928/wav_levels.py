#!/usr/bin/env python3
"""Measure peak and RMS level (dBFS) and duration of candidate Windows notification sounds. Read-only."""
import glob, math, struct, wave
from pathlib import Path

media = Path(glob.glob("/mnt/c/Windows/Media")[0])
names = ["Windows Notify System Generic.wav", "Windows Notify Messaging.wav", "Windows Notify Calendar.wav",
         "Windows Notify Email.wav", "Windows Notify.wav", "Windows Message Nudge.wav", "Windows Ding.wav",
         "Windows Background.wav", "ding.wav", "chimes.wav", "notify.wav", "Speech On.wav", "Speech Off.wav",
         "Windows Balloon.wav", "Windows Navigation Start.wav", "Windows Pop-up Blocked.wav"]

def level(path):
    with wave.open(str(path), "rb") as w:
        n, width, ch, rate = w.getnframes(), w.getsampwidth(), w.getnchannels(), w.getframerate()
        raw = w.readframes(n)
    if width != 2:
        return None
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    peak = max(abs(s) for s in samples) or 1
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) or 1
    return round(20 * math.log10(peak / 32768), 1), round(20 * math.log10(rms / 32768), 1), round(n / rate, 2)

print("file | peak dBFS | rms dBFS | seconds")
rows = []
for name in names:
    p = media / name
    if not p.exists():
        continue
    try:
        res = level(p)
    except Exception as exc:  # non-PCM or unreadable
        res = None
    rows.append((name, res))
    print(name, "|", res if res else "not 16-bit PCM / unreadable")
