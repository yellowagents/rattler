"""Receiver for seismological network datagrams

The protocol is intended to be able to describe accelerometrical activity in
general, which makes it very apt for recording and transmitting seismological
activity.

Module usage example:

.. code-block:: python

   import rattler

   for meas in rattler.measurements():
       print meas.timestamp, meas.values

Would output something like::

    2010-05-20 15:28:46.990220 (-0.03622, 0.05433, -0.97805)
    2010-05-20 15:28:47.005845 (-0.01811, 0.05433, -0.97805)
    2010-05-20 15:28:47.023423 (-0.01811, 0.05433, -0.97805)
    2010-05-20 15:28:47.041001 (-0.01811, 0.05433, -0.97805)
    2010-05-20 15:28:47.056626 (-0.01811, 0.05433, -0.97805)

But with much greater precision, as the numbers have been cut for brevity's
sake.
"""

# NOTE Remember to change version in setup.py as well.
__version__ = "1.0"

import socket
import struct
import datetime

class RattlerException(StandardError):
    pass

class PartialData(RattlerException):
    def __init__(self, num_got, num_want, data):
        self.num_got = num_got
        self.num_want = num_want
        self.data = data
        super(PartialData, self).__init__("wanted %d bytes, got %d"
                                          % (num_got, num_want))

class StructFormat(str):
    """Convenience object layer for procedural struct module."""
    def _get_size(self):
        return struct.calcsize(self)
    size = property(_get_size)

    def unpack_split(self, data):
        """Unpack own format from *data* and return (v, remainder)"""
        part, rest = data[:self.size], data[self.size:]
        return (struct.unpack(self, part), rest)

def hasattrs(obj, attrs):
    for attr in attrs:
        if not hasattr(obj, attr):
            return False
    return True

class Measurement(object):
    """A seismological measurement"""

    __slots__ = ("source", "timestamp", "x", "y", "z")

    def __init__(self, timestamp, x, y, z, source=None):
        self.timestamp = timestamp
        self.x, self.y, self.z = x, y, z
        self.source = source

    def clone(self, x, y, z):
        """Make a copy of this instance with new accelerometer data."""
        return type(self)(self.timestamp, x, y, z, source=self.source)

    def __str__(self):
        r = "<Measurement at %s" % (self.timestamp,)
        if self.source:
            r += " from %s" % (self.source,)
        r += ": (%+.6f, %+.6f, %+.6f)>" % (self.x, self.y, self.z)
        return r

    def __add__(self, o):
        if not hasattrs(o, ("x", "y", "z")):
            return NotImplemented
        return self.clone(self.x + o.x, self.y + o.y, self.z + o.z)
    def __sub__(self, o):
        if not hasattrs(o, ("x", "y", "z")):
            return NotImplemented
        return self.clone(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, n):
        return self.clone(self.x * n, self.y * n, self.z * n)
    def __div__(self, n):
        return self.clone(self.x / n, self.y / n, self.z / n)
    __truediv__ = __div__

    def __neg__(self):
        return self.clone(-self.x, -self.y, -self.z)
    def __pos__(self):
        return self.clone(+self.x, +self.y, +self.z)
    def __abs__(self):
        return self.clone(abs(self.x), abs(self.y), abs(self.z))
    def __invert__(self):
        return self.clone(~self.x, ~self.y, ~self.z)

    @property
    def values(self):
        return (self.x, self.y, self.z)

wrapper_fmt = StructFormat("! HH")
measurement_fmt = StructFormat("! f 3d")

def unpack_wrapper(msg):
    """Unpack the wrapper data for *msg*.

    The wrapper data consists of a message type and its size. This is returned
    as a two-tuple of (typ, data).

    If *msg* doesn't contain the whole message, a PartialData exception is
    raised.
    """
    (typ, sz), rest = wrapper_fmt.unpack_split(msg)
    if len(msg) != sz:
        raise PartialData(sz, len(rest), msg)
    return (typ, rest)

def unpack_measurement(msg):
    """Unpack the data of a measurement from *msg* into a four-tuple of
    (reltime, x, y, z).
    """
    rv, rest = measurement_fmt.unpack_split(msg)
    if rest:
        raise ValueError("got excess data %r" % (rest,))
    return rv

class SeismometerReceiver(object):
    msgtype_announce = (1 << 0)
    msgtype_measurement = (1 << 1)

    #: If True, measurements that are older than a previously seen measurement
    # will be ignored.
    drop_on_backward = True

    def __init__(self, ipv6=False, bind="0.0.0.0", port=5612):
        #: _first tracks what time difference there is between the seismometer
        # data and the local time. The seismometer's timestamps are based on
        # some arbitrary point in time.
        self._first = None
        self._prev_dt = None
        addrfam = socket.AF_INET
        if ipv6:
            addrfam = socket.AF_INET6
        self.sock = socket.socket(addrfam, socket.SOCK_DGRAM, 0)
        self.sock.bind((bind, port))

    def compensate_time(self, ts):
        if not self._first:
            (base_dt, base_ts) = (datetime.datetime.now(), ts)
            self._first = (base_dt, base_ts)
        else:
            (base_dt, base_ts) = self._first
        diff = ts - base_ts
        secs = int(diff)
        msecs = (diff % 1) * (10 ** 6)
        delta = datetime.timedelta(seconds=secs, microseconds=msecs)
        return base_dt + delta

    def receive(self):
        (data, addr) = self.sock.recvfrom(4096)
        typ, msg = unpack_wrapper(data)
        if typ == self.msgtype_announce:
            raise NotImplementedError("in the future!")
        elif typ == self.msgtype_measurement:
            (timestamp, x, y, z) = unpack_measurement(msg)
            timestamp = self.compensate_time(timestamp)
            if self.drop_on_backward:
                if self._prev_dt and timestamp < self._prev_dt:
                    return
                self._prev_dt = timestamp
            return Measurement(timestamp, x, y, z, source=addr)

def measurements():
    """Generator for measurement objects."""
    sr = SeismometerReceiver()
    while True:
        m = sr.receive()
        if m is None:
            continue
        yield m

if __name__ == "__main__":
    import sys

    outf = sys.stdout

    if sys.platform != "win32":
        outf.write("Awaiting initial measurement...")
        outf.flush()

    for meas in measurements():
        if sys.platform != "win32":
            # The ANSI control code 2K clears the current line.
            outf.write("\x1b[2K\r%s" % (meas,))  
        else:
            outf.write(str(meas) + "\n")
        outf.flush()
