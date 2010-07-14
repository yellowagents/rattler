import sys
import datetime
from collections import deque
from math import sqrt

import rattler

# {{{ Utilities

def memorizer(iter, backlog=20):
    prev_vals = deque()
    for value in iter:
        prev_vals.append(value)
        while len(prev_vals) > backlog:
            prev_vals.popleft()
        yield list(prev_vals)

def medians(iter, backlog=20):
    for vals in memorizer(iter, backlog=backlog):
        vals.sort()
        mid_idx = len(vals) / 2
        if len(vals) & 1:
            yield vals[mid_idx]
        else:
            yield (vals[mid_idx - 1] + vals[mid_idx]) / 2.0

def ri(v): return int(round(v))
def dt2secs(dt):
    rv = (dt.days * 24 * 3600)
    rv += dt.seconds
    rv += dt.microseconds / 1000000.0
    return rv

# }}}

# {{{ pygame initialization

import pygame
from pygame import draw, display, rect
from pygame.locals import SWSURFACE, FULLSCREEN, HWSURFACE, DOUBLEBUF

pygame.init()
fullscreen = False

if fullscreen:
    depth = 0
    flags = FULLSCREEN | HWSURFACE | DOUBLEBUF
else:
    depth = 16
    flags = SWSURFACE | DOUBLEBUF

modes = display.list_modes(depth, flags)
if fullscreen:
    if modes == -1:  # Welcome to exceptionlessland
        raise SystemExit("Failed to initialize display")
    else:
        mode = max(modes)
else:
    mode = (640, 480)

display.set_mode(mode, flags)
screen = display.get_surface()
width, height = screen.get_size()

# }}}

fg = (0x30, 0x30, 0x30)
bg = (0xef, 0xef, 0xef)
cross_cl = (0xb0, 0xb0, 0xb0)

size = rect.Rect((0, 0), screen.get_size())
r1 = rect.Rect(size.topleft, size.center)
r2 = rect.Rect(size.midtop, size.center)
r3 = rect.Rect(size.midleft, size.center)
r4 = rect.Rect(size.center, size.center)
rs = (r1, r2, r3, r4)

views = ((r1, ("x", "y")),
         (r2, ("x", "z")),
         (r3, ("y", "z")),
         (r4, (None, None)))

# This is a simple 2D vector
class Vector(object):
    __slots__ = ("_x", "_y", "_length")

    def __init__(self, x, y):
        self._x, self._y = x, y
        self._length = sqrt(self.x ** 2 + self.y ** 2)

    @property
    def x(self): return self._x
    @property
    def y(self): return self._y
    @property
    def length(self): return self._length

    def normalized(self):
        return type(self)(self.x / self.length, self.y / self.length)

class LoopLatencies(object):
    clocksource = datetime.datetime.now

    def __init__(self):
        self.reset()

    def reset(self):
        self.start = self.clocksource()

    def __iter__(self):
        return self

    def next(self):
        dt = self.clocksource() - self.start
        latencies.reset()
        return dt2secs(dt)

latencies = LoopLatencies()
latency_medians = medians(latencies)

bg_r = r1.copy().move(0, 0)
line_len = min(bg_r.w, bg_r.h) / 2.0

bg_surf = pygame.Surface(bg_r.size, HWSURFACE)
bg_surf.fill(bg)
draw.circle(bg_surf, cross_cl, bg_r.center, ri(line_len), 1)
draw.line(bg_surf, cross_cl, (bg_r.left, bg_r.centery), (bg_r.right, bg_r.centery))
draw.line(bg_surf, cross_cl, (bg_r.centerx, bg_r.top), (bg_r.centerx, bg_r.bottom))
draw.rect(bg_surf, cross_cl, bg_r, 2)

n_skips = 0
for meas in rattler.measurements():
    lat = latency_medians.next()
    sys.stdout.write("\x1b[2K\rlatency = %.4fms" % (lat * 1000,))
    sys.stdout.flush()

    # Try to keep synchronized
    curr_ts = datetime.datetime.now()
    secs_ago = dt2secs(curr_ts - meas.timestamp)
    if secs_ago > (lat * 1.25):
        n_skips += 1
        sys.stdout.write(", skips = %d" % (n_skips,))
        sys.stdout.flush()
        continue
    else:
        n_skips = 0

    for (r, (va1, va2)) in views:
        if va1 is va2 is None:
            draw.rect(screen, bg, r)
            continue

        screen.blit(bg_surf, r.topleft)

        vec = Vector(getattr(meas, va1), getattr(meas, va2))

        if vec.length < 0.075:
            continue

        vec = vec.normalized()

        draw.line(screen, fg, r.center,
                  (ri(r.centerx + vec.x * line_len),
                   ri(r.centery + vec.y * line_len)))

    display.flip()
