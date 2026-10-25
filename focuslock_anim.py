"""A small animation toolkit for Tkinter: tweens, easing curves, colour
blending, and a few reusable effects (fade-in, shake, typewriter, confetti).

Frames are scheduled on the root window's after(), never the animated
widget's own: tkinter deletes a widget's after-callbacks when it's destroyed,
and a pending one then fires as an "invalid command name" Tcl error. Each
frame instead checks the widget still exists and stops quietly if not --
FocusLock rebuilds whole views on refresh and theme toggles, so widgets
vanishing mid-animation is routine, not an error.
"""
import math
import random
import time
import tkinter as tk

FRAME_MS = 16          # ~60fps for short tweens
IDLE_FRAME_MS = 33     # ~30fps is plenty for slow ambient loops


# ---------- easing ----------

def linear(t):
    return t


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t, s=1.70158):
    t -= 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def ease_out_bounce(t):
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


# ---------- colour ----------

_rgb_cache = {}


def to_rgb(color, widget=None):
    """'#rrggbb' (fast path) or any Tk colour name (needs a widget) -> (r, g, b)."""
    if color in _rgb_cache:
        return _rgb_cache[color]
    if isinstance(color, str) and len(color) == 7 and color[0] == "#":
        rgb = (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    elif widget is not None:
        r, g, b = widget.winfo_rgb(color)
        rgb = (r >> 8, g >> 8, b >> 8)
    else:
        raise ValueError(f"can't resolve colour {color!r} without a widget")
    _rgb_cache[color] = rgb
    return rgb


def rgb_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def blend(c1, c2, t, widget=None):
    """Colour t of the way from c1 to c2 (t outside 0..1 is clamped)."""
    t = max(0.0, min(1.0, t))
    return rgb_hex(mix(to_rgb(c1, widget), to_rgb(c2, widget), t))


def lighten(color, amount=0.18):
    return blend(color, "#ffffff", amount)


# ---------- core runners ----------

class Anim:
    """Handle for a running animation; cancel() stops it."""

    def __init__(self, widget):
        self.widget = widget
        self.root = widget._root()
        self.after_id = None
        self.cancelled = False
        self.t0 = 0.0

    def cancel(self):
        self.cancelled = True
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass


def _alive(widget):
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def animate(widget, duration_ms, on_frame, on_done=None, easing=ease_out_cubic, delay_ms=0):
    """Call on_frame(eased_t) every frame for duration_ms, then on_done()."""
    anim = Anim(widget)

    def step():
        if anim.cancelled or not _alive(widget):
            return
        raw = 1.0 if duration_ms <= 0 else min(1.0, (time.perf_counter() - anim.t0) * 1000.0 / duration_ms)
        try:
            on_frame(easing(raw))
            if raw < 1.0:
                anim.after_id = anim.root.after(FRAME_MS, step)
            elif on_done:
                on_done()
        except tk.TclError:
            pass  # something it touched was destroyed between frames

    def start():
        anim.t0 = time.perf_counter()
        step()

    if delay_ms > 0:
        anim.after_id = anim.root.after(delay_ms, start)
    else:
        start()
    return anim


def loop(widget, period_ms, on_frame, delay_ms=0):
    """Call on_frame(phase) forever, phase cycling 0..1 every period_ms."""
    anim = Anim(widget)

    def step():
        if anim.cancelled or not _alive(widget):
            return
        phase = ((time.perf_counter() - anim.t0) * 1000.0 % period_ms) / period_ms
        try:
            on_frame(phase)
            anim.after_id = anim.root.after(IDLE_FRAME_MS, step)
        except tk.TclError:
            pass

    def start():
        anim.t0 = time.perf_counter()
        step()

    if delay_ms > 0:
        anim.after_id = anim.root.after(delay_ms, start)
    else:
        start()
    return anim


# ---------- effects ----------

COLOR_OPTIONS = (
    "bg", "fg", "highlightbackground", "highlightcolor", "insertbackground",
    "activebackground", "activeforeground", "buttonbackground",
    "selectbackground", "selectforeground", "disabledforeground",
)


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def fade_in(root, from_color, duration_ms=420, delay_ms=0):
    """Fade a widget and all its descendants in from from_color.

    Tk has no per-widget opacity, so this tweens every colour option from the
    background colour to its real value. Custom canvas widgets that draw their
    own items expose set_fade(t) and are driven through that instead.
    Colours are hidden immediately, so a delayed fade doesn't flash first.

    Fades may overlap (a row fading in inside a card that's also fading in).
    While a fade is in flight, each widget keeps its real colours in
    _fade_targets, and any other fade reads those instead of the
    temporarily-hidden ones -- otherwise the later fade would "restore" the
    hidden colour and leave the widget invisible for good."""
    jobs, hooks = [], []
    start_rgb = to_rgb(from_color, root)
    for w in walk(root):
        if isinstance(w, tk.Toplevel) and w is not root:
            continue
        if hasattr(w, "set_fade"):
            hooks.append(w)
            w.set_fade(0.0)
        try:
            keys = set(w.keys())
        except tk.TclError:
            continue
        targets = w.__dict__.setdefault("_fade_targets", {})
        for opt in COLOR_OPTIONS:
            if opt not in keys:
                continue
            try:
                if opt in targets:
                    end = targets[opt][0]
                else:
                    val = w.cget(opt)
                    if not val:
                        continue
                    end = to_rgb(str(val), w)
                w.configure({opt: rgb_hex(start_rgb)})
            except (tk.TclError, ValueError):
                continue
            count = targets[opt][1] + 1 if opt in targets else 1
            targets[opt] = (end, count)
            jobs.append((w, opt, end))

    def frame(t):
        for w, opt, end in jobs:
            try:
                w.configure({opt: rgb_hex(mix(start_rgb, end, t))})
            except tk.TclError:
                pass
        for h in hooks:
            try:
                h.set_fade(t)
            except tk.TclError:
                pass

    def done():
        # This fade no longer holds these colours; the last one out clears them.
        for w, opt, _ in jobs:
            targets = w.__dict__.get("_fade_targets", {})
            if opt in targets:
                end, count = targets[opt]
                if count <= 1:
                    del targets[opt]
                else:
                    targets[opt] = (end, count - 1)

    return animate(root, duration_ms, frame, on_done=done, delay_ms=delay_ms)


def fade_to(root, to_color, duration_ms=220, on_done=None):
    """The reverse of fade_in: tween a widget tree's colours to to_color
    (e.g. the background, so everything melts away), then on_done()."""
    jobs, hooks = [], []
    end_rgb = to_rgb(to_color, root)
    for w in walk(root):
        if isinstance(w, tk.Toplevel) and w is not root:
            continue
        if hasattr(w, "set_fade"):
            hooks.append(w)
        try:
            keys = set(w.keys())
        except tk.TclError:
            continue
        for opt in COLOR_OPTIONS:
            if opt not in keys:
                continue
            try:
                val = w.cget(opt)
                if val:
                    jobs.append((w, opt, to_rgb(str(val), w)))
            except (tk.TclError, ValueError):
                continue

    def frame(t):
        for w, opt, start in jobs:
            try:
                w.configure({opt: rgb_hex(mix(start, end_rgb, t))})
            except tk.TclError:
                pass
        for h in hooks:
            try:
                h.set_fade(1 - t)
            except tk.TclError:
                pass

    return animate(root, duration_ms, frame, on_done=on_done)


def _padx_pair(widget):
    padx = widget.pack_info().get("padx", 0)
    if isinstance(padx, (tuple, list)):
        return int(padx[0]), int(padx[-1])
    if isinstance(padx, str) and " " in padx:
        left, right = padx.split()
        return int(left), int(right)
    return int(padx), int(padx)


def shake(widget, amplitude=10, duration_ms=450, cycles=4):
    """Horizontal 'no' shake for a pack()ed widget, done by shifting its padx.
    The widget needs padx >= amplitude on both sides to move fully."""
    # Remember the resting padding on the widget, so a shake started while
    # another is mid-swing doesn't adopt the shifted padding as its rest.
    previous = getattr(widget, "_shake_anim", None)
    if previous:
        previous.cancel()
    if not hasattr(widget, "_shake_rest"):
        widget._shake_rest = _padx_pair(widget)
    left, right = widget._shake_rest

    def frame(t):
        dx = int(round(amplitude * math.sin(t * cycles * 2 * math.pi) * (1 - t)))
        dx = max(-left, min(right, dx))
        widget.pack_configure(padx=(left + dx, right - dx))

    widget._shake_anim = animate(widget, duration_ms, frame, easing=linear,
                                 on_done=lambda: widget.pack_configure(padx=(left, right)))
    return widget._shake_anim


def typewriter(label, text, ms_per_char=55, delay_ms=0, cursor="▌", blinks=4):
    """Type text into a label with a block cursor that blinks a few times.

    Pads with spaces to a constant length, so with a monospace font the label
    never changes width (no jitter in centred layouts) while it types."""
    n = len(text)
    label.configure(text=" " * (n + 1))

    def frame(t):
        k = int(round(n * t))
        label.configure(text=text[:k] + (cursor if cursor else " ") + " " * (n - k))

    def done():
        if not cursor or blinks <= 0:
            label.configure(text=text + " ")
            return
        state = {"i": 0}

        def blink():
            if not _alive(label):
                return
            i = state["i"]
            if i >= blinks * 2:
                label.configure(text=text + " ")
                return
            label.configure(text=text + (" " if i % 2 == 0 else cursor))
            state["i"] += 1
            label._root().after(330, blink)

        blink()

    return animate(label, ms_per_char * n, frame, on_done=done, easing=linear, delay_ms=delay_ms)


def pulse(widget, option, peak_color, base_color, duration_ms=420):
    """Flash a colour option to peak_color, then ease back to base_color."""
    def frame(t):
        widget.configure({option: blend(peak_color, base_color, t, widget)})
    widget.configure({option: peak_color})
    return animate(widget, duration_ms, frame)


def confetti(canvas, x, y, colors, fade_to, count=80, duration_ms=1900):
    """Burst of spinning confetti from (x, y) on a canvas, fading out."""
    parts = []
    for _ in range(count):
        ang = random.uniform(-math.pi * 0.92, -math.pi * 0.08)  # upward fan
        speed = random.uniform(6.0, 15.0)
        color = random.choice(colors)
        is_dot = random.random() < 0.3
        size = random.uniform(4.0, 8.0)
        item = (canvas.create_oval(0, 0, 0, 0, fill=color, outline="")
                if is_dot else canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill=color, outline=""))
        parts.append({
            "item": item, "x": x, "y": y, "dot": is_dot, "size": size, "color": color,
            "vx": math.cos(ang) * speed, "vy": math.sin(ang) * speed,
            "rot": random.uniform(0, math.pi), "vrot": random.uniform(-0.35, 0.35),
        })
    clock = {"last": time.perf_counter()}

    def frame(t):
        now = time.perf_counter()
        dt = min(0.05, now - clock["last"]) * 60.0  # in 60fps-frame units
        clock["last"] = now
        fade = max(0.0, (t - 0.55) / 0.45)
        for p in parts:
            p["vy"] += 0.42 * dt
            p["vx"] *= 0.985 ** dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["rot"] += p["vrot"] * dt
            s, px, py = p["size"], p["x"], p["y"]
            if p["dot"]:
                canvas.coords(p["item"], px - s / 2, py - s / 2, px + s / 2, py + s / 2)
            else:
                c, si = math.cos(p["rot"]), math.sin(p["rot"])
                hw, hh = s, s * 0.5
                pts = []
                for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                    pts += [px + dx * c - dy * si, py + dx * si + dy * c]
                canvas.coords(p["item"], *pts)
            if fade:
                canvas.itemconfigure(p["item"], fill=blend(p["color"], fade_to, fade))

    def done():
        for p in parts:
            canvas.delete(p["item"])

    return animate(canvas, duration_ms, frame, on_done=done, easing=linear)
