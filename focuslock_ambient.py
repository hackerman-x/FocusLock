"""Focus sounds: ambient loops (rain, ocean, fireplace, forest, café, noise
colours and more) made from scratch -- no audio files ship with FocusLock -- and cached as WAVs in
~/.cache/focuslock/ambient.

Playback streams the loop forever into a command-line player's stdin
(PipeWire's pw-cat, else PulseAudio's pacat, else ALSA's aplay), so it's
seamless, and volume changes / stopping fade smoothly instead of clicking.
All of it runs on a background thread; nothing here touches Tk.
"""
import array
import math
import os
import random
import shutil
import threading
import time
import wave

import focuslock_platform as plat

try:
    import numpy as np
except ImportError:  # works without numpy, just generates more slowly
    np = None

RATE = 44100
LOOP_SECONDS = 30 if np is not None else 12
VERSION = 1
CACHE_DIR = os.path.join(plat.CACHE_DIR, "ambient", f"v{VERSION}")

# Overall output level for focus sounds. They play for hours under your
# work, so even full volume on the slider stays well below the app's other
# sounds.
OUTPUT_GAIN = 0.45

SOUNDS = [("rain", "Rain"), ("storm", "Thunderstorm"), ("waves", "Ocean"), ("stream", "Stream"),
          ("forest", "Forest"), ("night", "Night"), ("fire", "Fireplace"), ("cafe", "Café"), ("fan", "Fan"),
          ("brown", "Brown noise"), ("pink", "Pink noise"), ("white", "White noise"),
          # unlocked by focus hours (see focuslock_core.REWARDS)
          ("library", "Library"), ("space", "Space station"), ("train", "Night train")]


# ---------- synthesis ----------
# With numpy, sounds are shaped in the frequency domain: an FFT of white
# noise is reshaped and transformed back. The result is periodic, so the
# loop repeats with no seam at all, and 30 s take well under a second.
# Without numpy there's a slower sample-by-sample fallback.

def _shaped_noise(n, rng, shape):
    """Noise whose amplitude spectrum follows shape(freqs_hz); periodic in n."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / RATE)
    spec *= shape(np.maximum(f, 1.0))
    x = np.fft.irfft(spec, n)
    return x / max(1e-9, float(np.max(np.abs(x))))


def _bursts(n, rng, per_sec, length_s, decay, gains, bright):
    """Sparse decaying noise bursts (drops, crackles), placed circularly so
    they wrap around the loop point like everything else."""
    impulses = np.zeros(n)
    count = int(per_sec * n / RATE)
    idx = rng.integers(0, n, count)
    impulses[idx] = rng.uniform(gains[0], gains[1], count) * rng.choice([-1, 1], count)
    k = int(length_s * RATE)
    kernel = np.zeros(n)
    burst = rng.standard_normal(k) * np.exp(-decay * np.arange(k) / RATE)
    if bright:  # first difference = brighter, snappier
        burst = np.diff(burst, prepend=0.0)
    kernel[:k] = burst
    return np.fft.irfft(np.fft.rfft(impulses) * np.fft.rfft(kernel), n)


def _scatter(n, rng, count, make):
    """Add count events (make(rng) -> samples) at random spots, wrapping
    around the loop point so the loop stays seamless."""
    out = np.zeros(n)
    for _ in range(count):
        sig = make(rng)
        start = int(rng.integers(0, n))
        idx = (start + np.arange(len(sig))) % n
        np.add.at(out, idx, sig)
    return out


def _slow_noise(n, rng, seconds, lo, hi, rate=200):
    """A slowly wandering, loop-periodic random envelope (lo..hi Hz), made at
    a low sample rate and stretched to n samples -- far cheaper than shaping
    full-rate noise for something that only changes a few times a second."""
    m = int(seconds * rate)
    spec = np.fft.rfft(rng.standard_normal(m))
    f = np.fft.rfftfreq(m, 1 / rate)
    spec *= (f >= lo) * (f <= hi)
    env = np.fft.irfft(spec, m)
    env /= max(1e-9, float(np.max(np.abs(env))))
    pos = np.arange(n) * (m / n)
    return np.interp(pos, np.arange(m + 1), np.append(env, env[0]))


def _loop_hz(hz, seconds):
    """The nearest frequency that fits a whole number of cycles in the loop."""
    return max(1, round(hz * seconds)) / seconds


def _chirp(f0, f1, length, rng=None, decay=None):
    """A short sine sweep from f0 to f1 Hz with a soft envelope."""
    k = max(2, int(length * RATE))
    t = np.arange(k) / RATE
    freq = f0 + (f1 - f0) * (t / length)
    env = np.sin(np.pi * np.arange(k) / k) ** 2
    if decay:
        env *= np.exp(-t * decay)
    return np.sin(2 * np.pi * np.cumsum(freq) / RATE) * env


def _normalize(x, rms=0.2):
    """Level by loudness (RMS) so every sound sits at a similar volume, then
    keep the rare peaks (a bird, a clink) from clipping."""
    x = x - x.mean()
    x = x * (rms / max(1e-9, float(np.sqrt(np.mean(x ** 2)))))
    peak = float(np.max(np.abs(x)))
    return np.tanh(x / 0.9) * 0.9 if peak > 0.9 else x


def _audible(f, low=45):
    """Fade out content below low Hz -- sub-bass laptop and headphone
    speakers can't reproduce, which would just waste the loudness."""
    return np.clip(f / low, 0, 1) ** 2


def _make_numpy(name, seconds):
    n = int(seconds * RATE)
    rng = np.random.default_rng(7)
    t = np.arange(n) / RATE
    if name == "brown":
        x = _shaped_noise(n, rng, lambda f: _audible(f) / np.maximum(f, 90))
    elif name == "rain":
        hiss = _shaped_noise(n, rng, lambda f: np.clip(f / 600, 0, 1) ** 2 * f ** -0.5 / (1 + (f / 4500) ** 2))
        body = _shaped_noise(n, rng, lambda f: _audible(f, 80) / np.maximum(f, 150))
        drops = _bursts(n, rng, 55, 0.014, 320, (0.3, 1.0), True)
        near = _bursts(n, rng, 7, 0.03, 140, (0.6, 1.6), False)
        x = 0.55 * hiss + 0.35 * body + 0.18 * drops / max(1e-9, np.abs(drops).max()) \
            + 0.22 * near / max(1e-9, np.abs(near).max())
    elif name == "waves":
        rumble = _shaped_noise(n, rng, lambda f: _audible(f) / np.maximum(f, 80))
        wash = _shaped_noise(n, rng, lambda f: np.clip(f / 250, 0, 1) * f ** -0.8 / (1 + (f / 2500) ** 2))
        # Swell periods divide the loop length, so the loop stays seamless.
        phase = 2 * np.pi * t / (seconds / 3) + 0.7 * np.sin(2 * np.pi * t / seconds)
        swell = 0.5 - 0.5 * np.cos(phase)
        x = rumble * (0.3 + 0.7 * swell) + 0.9 * wash * swell ** 3
    elif name == "fire":
        rumble = _shaped_noise(n, rng, lambda f: _audible(f) / np.maximum(f, 70) * (f < 900))
        crackle = _bursts(n, rng, 12, 0.006, 1100, (0.2, 1.0), True)
        pops = _bursts(n, rng, 1.3, 0.025, 240, (0.5, 1.0), True)
        x = 0.45 * rumble + 0.45 * crackle / max(1e-9, np.abs(crackle).max()) \
            + 0.5 * pops / max(1e-9, np.abs(pops).max())
    elif name in EXTRA:
        return EXTRA[name](n, rng, t, seconds)
    else:
        raise ValueError(name)
    return 0.85 * x / max(1e-9, float(np.max(np.abs(x))))


def _white(n, rng, t, seconds):
    # Pure white noise is harsh; roll off the very top so it's a soft hiss.
    return _normalize(_shaped_noise(n, rng, lambda f: _audible(f) / np.sqrt(1 + (f / 9000) ** 2)), 0.17)


def _pink(n, rng, t, seconds):
    return _normalize(_shaped_noise(n, rng, lambda f: _audible(f) / np.sqrt(f)), 0.19)


def _fan(n, rng, t, seconds):
    air = _shaped_noise(n, rng, lambda f: _audible(f, 60) / np.maximum(f, 120) / (1 + (f / 3000) ** 2))
    hum = sum(a * np.sin(2 * np.pi * _loop_hz(hz, seconds) * t) for hz, a in ((100, 0.05), (200, 0.025), (300, 0.01)))
    blades = 1 + 0.06 * np.sin(2 * np.pi * _loop_hz(23, seconds) * t)   # gentle blade-pass flutter
    return _normalize(air * blades + hum, 0.2)


def _stream(n, rng, t, seconds):
    water = _shaped_noise(n, rng, lambda f: np.clip(f / 300, 0, 1) ** 2 / np.sqrt(f) / (1 + (f / 3500) ** 2))
    flow = 1 + 0.25 * np.sin(2 * np.pi * _loop_hz(0.37, seconds) * t) * np.sin(2 * np.pi * _loop_hz(0.11, seconds) * t)

    def bubble(r):
        f0 = r.uniform(350, 900)
        return _chirp(f0, f0 * r.uniform(1.4, 2.2), r.uniform(0.012, 0.035), decay=60) * r.uniform(0.2, 0.7)
    bubbles = _scatter(n, rng, int(45 * seconds), bubble)
    return _normalize(water * flow + 1.6 * bubbles / max(1e-9, np.abs(bubbles).max()) * np.abs(water).max(), 0.18)


def _forest(n, rng, t, seconds):
    leaves = _shaped_noise(n, rng, lambda f: np.clip(f / 200, 0, 1) / np.sqrt(f) / (1 + (f / 5000) ** 2))
    gust = 0.55 + 0.45 * (0.5 - 0.5 * np.cos(2 * np.pi * _loop_hz(1 / 7.5, seconds) * t)) ** 2

    def bird(r):
        f = r.uniform(2400, 4800)
        notes = []
        for _ in range(int(r.integers(2, 6))):
            notes.append(_chirp(f, f * r.uniform(0.8, 1.35), r.uniform(0.05, 0.12)) * r.uniform(0.4, 1.0))
            notes.append(np.zeros(int(r.uniform(0.03, 0.09) * RATE)))
        return np.concatenate(notes)
    birds = _scatter(n, rng, int(seconds / 2.0), bird)
    bed = leaves * gust
    return _normalize(bed + 0.9 * birds * np.abs(bed).max() / max(1e-9, np.abs(birds).max()), 0.16)


def _night(n, rng, t, seconds):
    air = _shaped_noise(n, rng, lambda f: _audible(f, 60) / np.maximum(f, 200) / (1 + (f / 2000) ** 2))
    crickets = np.zeros(n)
    for _ in range(3):   # a few crickets, each with its own pitch and rhythm
        pitch = rng.uniform(3800, 5200)
        period = rng.uniform(0.7, 1.3)
        pulse = np.sin(2 * np.pi * pitch * np.arange(int(0.018 * RATE)) / RATE) * np.hanning(int(0.018 * RATE))
        chirp = np.concatenate([np.concatenate([pulse, np.zeros(int(0.012 * RATE))]) for _ in range(int(rng.integers(3, 5)))])
        level = rng.uniform(0.3, 1.0)
        start = rng.uniform(0, period)
        k = start
        while k < seconds:
            i = int(k * RATE)
            idx = (i + np.arange(len(chirp))) % n
            np.add.at(crickets, idx, chirp * level * rng.uniform(0.7, 1.0))
            k += period * rng.uniform(0.92, 1.08)
    return _normalize(air + 0.25 * crickets * np.abs(air).max() / max(1e-9, np.abs(crickets).max()) * 3, 0.13)


def _cafe(n, rng, t, seconds):
    room = _shaped_noise(n, rng, lambda f: _audible(f, 60) / np.maximum(f, 150))
    babble = np.zeros(n)
    for _ in range(8):   # overlapping "voices": speech-band noise with a syllable-rate rhythm
        voice = _shaped_noise(n, rng, lambda f, c=rng.uniform(250, 600): np.exp(-((np.log(f) - np.log(c * 2)) ** 2) / 0.6))
        syll = _slow_noise(n, rng, seconds, 2, 7)       # syllables
        talk = _slow_noise(n, rng, seconds, 0, 0.25)    # who's talking right now
        babble += voice * np.clip(syll, 0, None) * np.clip(talk + 0.3, 0, None)

    def clink(r):
        f = r.uniform(2200, 4200)
        k = int(0.35 * RATE)
        tt = np.arange(k) / RATE
        return (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.7 * tt)) * np.exp(-tt * 18) * r.uniform(0.3, 1.0)
    clinks = _scatter(n, rng, int(seconds / 3.5), clink)
    babble = babble / max(1e-9, np.abs(babble).max())
    return _normalize(0.35 * room + babble + 0.25 * clinks / max(1e-9, np.abs(clinks).max()), 0.17)


def _storm(n, rng, t, seconds):
    rain = _make_numpy("rain", seconds)

    def thunder(r):
        length = r.uniform(3.5, 6.0)
        k = int(length * RATE)
        tt = np.arange(k) / RATE
        roll = np.fft.irfft(np.fft.rfft(r.standard_normal(k)) * (np.fft.rfftfreq(k, 1 / RATE) < 140), k)
        env = (1 - np.exp(-tt / 0.25)) * np.exp(-tt / (length / 3))
        env *= 0.6 + 0.4 * np.abs(np.sin(2 * np.pi * tt * r.uniform(0.6, 1.4)))   # rolling
        return roll * env
    rolls = _scatter(n, rng, 2, thunder)
    rolls = rolls / max(1e-9, np.abs(rolls).max())
    return _normalize(rain + 0.9 * rolls, 0.21)


def _library(n, rng, t, seconds):
    room = _shaped_noise(n, rng, lambda f: _audible(f, 60) / np.sqrt(f) / (1 + (f / 1200) ** 2))

    def page(r):   # a page turning: a soft papery swish
        k = int(r.uniform(0.25, 0.45) * RATE)
        sw = np.fft.irfft(np.fft.rfft(r.standard_normal(k)) * ((np.fft.rfftfreq(k, 1 / RATE) > 1500) &
                                                                  (np.fft.rfftfreq(k, 1 / RATE) < 7000)), k)
        env = np.sin(np.pi * np.arange(k) / k) ** 3 * (1 + 0.5 * np.sin(2 * np.pi * 23 * np.arange(k) / RATE))
        return sw * env * r.uniform(0.4, 1.0)

    def steps(r):  # two or three distant footsteps
        out = []
        for _ in range(int(r.integers(2, 4))):
            k = int(0.12 * RATE)
            tt = np.arange(k) / RATE
            out.append(np.sin(2 * np.pi * r.uniform(70, 110) * tt) * np.exp(-tt * 40) * r.uniform(0.5, 1.0))
            out.append(np.zeros(int(r.uniform(0.45, 0.6) * RATE)))
        return np.concatenate(out)
    pages = _scatter(n, rng, int(seconds / 7), page)
    walk = _scatter(n, rng, int(seconds / 12), steps)
    peak = np.abs(room).max()
    return _normalize(room + 0.6 * peak * pages / max(1e-9, np.abs(pages).max())
                      + 0.5 * peak * walk / max(1e-9, np.abs(walk).max()), 0.12)


def _space(n, rng, t, seconds):
    hum = sum(a * np.sin(2 * np.pi * _loop_hz(hz, seconds) * t + ph)
              for hz, a, ph in ((55, 0.5, 0), (110, 0.25, 1), (165, 0.08, 2), (55.4, 0.3, 0.5)))
    vent = _shaped_noise(n, rng, lambda f: _audible(f, 80) / np.maximum(f, 200) / (1 + (f / 1500) ** 2))

    def beep(r):
        f = r.choice([880, 1175, 1318, 1568])
        a = _chirp(f, f, 0.09) * 0.8
        b = _chirp(f * r.choice([0.75, 1.25, 1.5]), f * 1.0, 0.09) * 0.6
        return np.concatenate([a, np.zeros(int(0.05 * RATE)), b])
    beeps = _scatter(n, rng, int(seconds / 6), beep)
    x = 0.6 * hum / np.abs(hum).max() + vent / max(1e-9, np.abs(vent).max())
    return _normalize(x + 0.35 * beeps / max(1e-9, np.abs(beeps).max()), 0.15)


def _train(n, rng, t, seconds):
    rumble = _shaped_noise(n, rng, lambda f: _audible(f, 40) / np.maximum(f, 60) / (1 + (f / 600) ** 2))
    sway = 1 + 0.15 * np.sin(2 * np.pi * _loop_hz(0.23, seconds) * t)
    clacks = np.zeros(n)
    period = seconds / round(seconds / 1.7)   # wheels over rail joints, a whole number per loop
    k = int(0.06 * RATE)
    tt = np.arange(k) / RATE

    def clack():
        nz = np.fft.irfft(np.fft.rfft(rng.standard_normal(k)) * (np.fft.rfftfreq(k, 1 / RATE) < 2500), k)
        return (nz + 0.6 * np.sin(2 * np.pi * 180 * tt)) * np.exp(-tt * 55)
    start = 0.0
    while start < seconds - 1e-6:
        for off, g in ((0.0, 1.0), (0.17, 0.8), (period * 0.55, 0.9), (period * 0.55 + 0.17, 0.75)):   # da-dum ... da-dum
            i = int((start + off) * RATE)
            idx = (i + np.arange(k)) % n
            np.add.at(clacks, idx, clack() * g)
        start += period
    x = rumble * sway / np.abs(rumble).max()
    return _normalize(x + 0.5 * clacks / max(1e-9, np.abs(clacks).max()), 0.18)


EXTRA = {"white": _white, "pink": _pink, "fan": _fan, "stream": _stream, "forest": _forest,
         "night": _night, "cafe": _cafe, "storm": _storm, "library": _library, "space": _space, "train": _train}


def _make_python(name, seconds):
    """Slow fallback without numpy: brown-noise based variants, made
    seamless by crossfading the loop's end into its start."""
    rng = random.Random(7)
    fade = int(1.5 * RATE)
    n = int(seconds * RATE) + fade
    x, acc = [0.0] * n, 0.0
    for i in range(n):
        acc = 0.998 * acc + rng.gauss(0, 0.02)
        x[i] = acc
    if name in ("rain", "fire"):
        per_sec, length, decay = (45, 0.012, 380) if name == "rain" else (10, 0.006, 900)
        for _ in range(int(per_sec * n / RATE)):
            s0, g = rng.randrange(0, n - int(length * RATE)), rng.uniform(0.2, 0.8)
            for j in range(int(length * RATE)):
                x[s0 + j] += g * math.exp(-decay * j / RATE) * rng.uniform(-1, 1)
    elif name == "waves":
        for i in range(n):
            x[i] *= 0.3 + 0.7 * (0.5 - 0.5 * math.cos(2 * math.pi * i / RATE / 9.0))
    loop = int(seconds * RATE)
    out = x[:loop]
    for i in range(fade):
        r = i / fade
        out[i] = x[i] * r + x[loop + i] * (1 - r)
    mean = sum(out) / loop
    peak = max(1e-9, max(abs(v - mean) for v in out))
    return [0.85 * (v - mean) / peak for v in out]


def make_sound(name, seconds=None):
    """Samples (-1..1) for a seamless loop of the named sound."""
    seconds = seconds or LOOP_SECONDS
    return _make_numpy(name, seconds) if np is not None else _make_python(name, seconds)


def sound_path(name):
    return os.path.join(CACHE_DIR, f"{name}.wav")


def ensure_sound(name):
    """Generate and cache one sound if needed; returns its path."""
    path = sound_path(name)
    if os.path.exists(path):
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    samples = make_sound(name)
    if np is not None:
        data = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    else:
        data = array.array("h", (int(max(-1, min(1, v)) * 32767) for v in samples)).tobytes()
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    os.replace(tmp, path)
    return path


# ---------- playback ----------

def player_command():
    if shutil.which("pw-cat"):
        return ["pw-cat", "--playback", "--format", "s16", "--rate", str(RATE), "--channels", "1", "-"]
    if shutil.which("pacat"):
        return ["pacat", "--format=s16le", f"--rate={RATE}", "--channels=1", "--latency-msec=120"]
    if shutil.which("aplay"):
        return ["aplay", "-q", "-f", "S16_LE", "-r", str(RATE), "-c", "1"]
    return []


class AmbientPlayer:
    """Plays one ambient loop at a time. state: "idle" | "preparing" | "playing"."""

    CHUNK = RATE // 20          # 50 ms per write
    AHEAD = 0.25                # keep at most this many seconds buffered, so changes are quick

    def __init__(self):
        self.current = None
        self.state = "idle"
        self.volume = 0.5
        self.error = None
        self._stop = threading.Event()
        self._thread = None
        self._token = 0  # which play() call owns self.state; old threads leave it alone

    def play(self, name, volume=None):
        if volume is not None:
            self.volume = volume
        # Don't wait for the old sound: it fades out on its own thread while
        # the new one fades in, so switching is a quick crossfade, not a stall.
        self.stop()
        self._token += 1
        self.current = name
        self.state = "preparing"
        self.error = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(name, self._stop, self._token), daemon=True)
        self._thread.start()

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))

    def stop(self, wait=False):
        self._token += 1
        self._stop.set()
        if wait and self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.current = None
        self.state = "idle"

    def _run(self, name, stop, token):
        mine = lambda: token == self._token  # noqa: E731
        try:
            path = ensure_sound(name)
            with wave.open(path) as w:
                pcm = array.array("h", w.readframes(w.getnframes()))
        except (OSError, ValueError, wave.Error) as e:
            if mine():
                self.error, self.state = f"Couldn't prepare the sound: {e}", "idle"
            return
        if stop.is_set():
            return
        sink, error = plat.open_audio_sink(RATE, None if plat.IS_WINDOWS else player_command())
        if sink is None:
            if mine():
                self.error, self.state = error, "idle"
            return
        if mine():
            self.state = "playing"
        samples = np.frombuffer(pcm.tobytes(), dtype="<i2").astype(float) if np is not None else pcm
        pos, gain = 0, 0.0
        started = time.monotonic()
        written = 0.0
        try:
            while True:
                stopping = stop.is_set()
                target = 0.0 if stopping else OUTPUT_GAIN * self.volume ** 1.6  # perceptual-ish curve
                if stopping and gain < 0.003:
                    break
                end = pos + self.CHUNK
                if np is not None:
                    chunk = samples[pos:end] if end <= len(samples) else np.concatenate(
                        (samples[pos:], samples[: end - len(samples)]))
                    ramp = np.linspace(gain, gain + (target - gain) * 0.25, len(chunk))
                    data = (chunk * ramp).astype("<i2").tobytes()
                else:
                    idx = [(pos + i) % len(samples) for i in range(self.CHUNK)]
                    g2 = gain + (target - gain) * 0.25
                    data = array.array("h", (int(samples[j] * (gain + (g2 - gain) * k / self.CHUNK))
                                             for k, j in enumerate(idx))).tobytes()
                gain += (target - gain) * 0.25  # ~0.2 s glide on every change
                pos = end % len(samples)
                sink.write(data)
                written += self.CHUNK / RATE
                ahead = written - (time.monotonic() - started)
                if ahead > self.AHEAD:
                    time.sleep(ahead - self.AHEAD)
        except (BrokenPipeError, OSError):
            pass
        finally:
            sink.close()
            if mine():
                self.state = "idle"
