import sys
from collections import deque

import signal

def sigint(frame, signo):
    sys.stdout.write("\x1b[2K\rBye!\n")
    sys.exit(0)

signal.signal(signal.SIGINT, sigint)

def medians(iter, backlog=20):
    """Given an iterable, yields median values from the *backlog* number of
    last items.
    
    Every value taken from *iter* must be comparable to every other value from
    that place.
    """
    prev_vals = deque()
    for value in iter:
        prev_vals.append(value)
        while len(prev_vals) > backlog:
            prev_vals.popleft()
        # Median part, could be split out
        vals = list(prev_vals)
        vals.sort()
        mid_idx = len(vals) / 2
        if len(vals) & 1:
            yield vals[mid_idx]
        else:
            yield (vals[mid_idx - 1] + vals[mid_idx]) / 2.0

import rattler

for meas in medians(rattler.measurements()):
    adjs = []
    p = adjs.append

    # Use Z to determine facing direction
    if meas.z > 0.8:
        p("flat, display down")
    elif meas.z > 0.3:
        p("tilted, display down")
    elif meas.z < -0.8:
        p("flat, display up")
    elif meas.z < -0.3:
        p("tilted, display up")

    # Use X & Y to determine which side is down
    xy_tilt = ((abs(meas.x) + abs(meas.y)) / 2)
    if xy_tilt <= 0.2:
        p("lying down")
    elif meas.y < -0.8:
        p("standing")
    elif meas.y > 0.8:
        p("standing upside down")
    elif meas.x < -0.8:
        p("lying on left side")
    elif meas.x > 0.8:
        p("lying on right side")

    desc = ", ".join(adjs)
    sys.stdout.write("\x1b[2K\r" + desc)
    sys.stdout.flush()
