"""FocusLock's sound effects, synthesized from scratch (no audio files ship
with the app) and cached as small WAV files in ~/.cache/focuslock/sounds.

play() never blocks: it hands the file to the first available command-line
player (PipeWire's pw-play, PulseAudio's paplay, or ALSA's aplay) as a
detached process, and quietly does nothing if none exists or sound is muted.
"""
import array
import math
import os
import random
import shutil
import time
import wave

import focuslock_platform as plat

RATE = 44100
VERSION = 1  # bump when any sound below changes, so caches regenerate
CACHE_DIR = os.path.join(plat.CACHE_DIR, "sounds", f"v{VERSION}")
MASTER = 0.6  # overall loudness (fraction of full scale)
# Each sound is normalized to MASTER * its level here, so UI ticks stay
# quiet and only the big moments (lock, badge, chime) are fuller.
LEVELS = {"click": 0.4, "tab": 0.35, "toggle_on": 0.35, "toggle_off": 0.35,
          "lock": 0.85, "chime": 0.7, "badge": 0.7, "error": 0.55}

enabled = True
_last_played = {}
_player = None


# ---------- synthesis ----------

def _tone(freq, seconds, amp=0.5, decay=8.0, attack=0.004, glide_to=None, harmonics=((1, 1.0),), shape="sine"):
    """One note: an exponentially decaying tone, optionally gliding in
    pitch, built from the given (multiple, weight) harmonics."""
    n = int(RATE * seconds)
    out = [0.0] * n
    phase = 0.0
    end = glide_to or freq
    for i in range(n):
        t = i / RATE
        f = freq + (end - freq) * (i / n)
        phase += 2 * math.pi * f / RATE
        env = math.exp(-decay * t) * (min(1.0, t / attack) if attack else 1.0)
        s = 0.0
        for mult, weight in harmonics:
            p = phase * mult
            if shape == "triangle":
                s += weight * (2 / math.pi) * math.asin(math.sin(p))
            else:
                s += weight * math.sin(p)
        out[i] = amp * env * s
    return out


def _noise(seconds, amp=0.3, decay=60.0, seed=1):
    rng = random.Random(seed)
    n = int(RATE * seconds)
    out, prev = [0.0] * n, 0.0
    for i in range(n):
        # Differencing white noise tilts it toward a crisp, high "tick".
        w = rng.uniform(-1, 1)
        out[i] = amp * math.exp(-decay * i / RATE) * (w - prev)
        prev = w
    return out


def _mix(*layers):
    """layers: (offset_seconds, samples) pairs, summed into one track."""
    length = max(int(off * RATE) + len(s) for off, s in layers)
    out = [0.0] * length
    for off, samples in layers:
        start = int(off * RATE)
        for i, v in enumerate(samples):
            out[start + i] += v
    return out


def _fade_tail(samples, seconds=0.01):
    n = min(len(samples), int(RATE * seconds))
    for i in range(n):
        samples[-1 - i] *= i / n
    return samples


SOUNDS = {
    # General button press: a short, soft tick.
    "click": lambda: _mix((0, _noise(0.03, 0.22, 140, seed=3)),
                          (0, _tone(1900, 0.03, 0.12, decay=120))),
    # Tab switch: a tiny downward blip.
    "tab": lambda: _tone(1500, 0.06, 0.22, decay=55, glide_to=1050),
    # Switch flipped on / off: two quick notes, rising or falling.
    "toggle_on": lambda: _mix((0, _tone(660, 0.07, 0.2, decay=45)), (0.045, _tone(990, 0.09, 0.2, decay=40))),
    "toggle_off": lambda: _mix((0, _tone(990, 0.07, 0.2, decay=45)), (0.045, _tone(620, 0.09, 0.2, decay=40))),
    # Lock engaged: a low thunk plus a metallic latch click.
    "lock": lambda: _mix(
        (0, _tone(140, 0.32, 0.6, decay=14, glide_to=65)),
        (0, _noise(0.05, 0.25, 90, seed=7)),
        (0.06, _tone(1850, 0.18, 0.12, decay=30, harmonics=((1, 1.0), (1.47, 0.6), (2.3, 0.3)))),
    ),
    # Lock finished: a bright rising arpeggio that rings out.
    "chime": lambda: _mix(*[
        (i * 0.09, _tone(f, 0.9, 0.17, decay=4.5, harmonics=((1, 1.0), (2, 0.25), (3, 0.08))))
        for i, f in enumerate((523.25, 659.25, 783.99, 1046.5))
    ]),
    # Badge unlocked: a quicker, higher sparkle with a shimmer on top.
    "badge": lambda: _mix(
        *[(i * 0.065, _tone(f, 0.8, 0.15, decay=5, harmonics=((1, 1.0), (2, 0.3), (4, 0.1))))
          for i, f in enumerate((783.99, 987.77, 1174.66, 1567.98))],
        (0.26, _tone(3136, 0.6, 0.05, decay=6, harmonics=((1, 1.0), (1.5, 0.5)))),
    ),
    # Something went wrong: two short buzzy notes, falling.
    "error": lambda: _mix((0, _tone(330, 0.13, 0.22, decay=18, shape="triangle")),
                          (0.12, _tone(233, 0.2, 0.22, decay=14, shape="triangle"))),
}


def _write_wav(path, samples, level):
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = MASTER * level * 32767 / peak
    data = array.array("h", (int(s * scale) for s in _fade_tail(samples)))
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    os.replace(tmp, path)


def sound_path(name):
    return os.path.join(CACHE_DIR, f"{name}.wav")


def ensure_sounds():
    """Synthesize any sound not already cached. Returns the cache dir."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    for name, make in SOUNDS.items():
        path = sound_path(name)
        if not os.path.exists(path):
            _write_wav(path, make(), LEVELS.get(name, 0.5))
    return CACHE_DIR


# ---------- playback ----------

def _find_player():
    for cmd in (["pw-play"], ["paplay"], ["aplay", "-q"]):
        if shutil.which(cmd[0]):
            return cmd
    return []


def play(name, min_gap=0.05):
    """Play a sound without blocking. Repeats of the same sound within
    min_gap seconds are dropped, so rapid events don't pile up."""
    global _player
    if not enabled or name not in SOUNDS:
        return
    now = time.monotonic()
    if now - _last_played.get(name, 0.0) < min_gap:
        return
    _last_played[name] = now
    if _player is None:
        _player = [] if plat.IS_WINDOWS else _find_player()
    if not _player and not plat.IS_WINDOWS:
        return
    path = sound_path(name)
    try:
        if not os.path.exists(path):
            ensure_sounds()
        plat.play_wav(path, _player)
    except (OSError, RuntimeError):   # RuntimeError: winsound with no audio device
        pass
