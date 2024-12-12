from ophyd import Device, EpicsSignal, Component as Cpt, PVPositionerPC
from ophyd.status import SubscriptionStatus
import bluesky.plan_stubs as bps
import time


class EPS_Shutter(Device):
    state = Cpt(EpicsSignal, "Pos-Sts")
    cls = Cpt(EpicsSignal, "Cmd:Cls-Cmd")
    opn = Cpt(EpicsSignal, "Cmd:Opn-Cmd")
    error = Cpt(EpicsSignal, "Err-Sts")
    maxcount = 3
    # openval = 1  # normal shutter values, FS1 is reversed
    # closeval = 0

    def __init__(self, *args, openval=1, closeval=0, shutter_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.openval = openval
        self.closeval = closeval
        self.shutter_type = shutter_type

    def status(self):
        if self.state.get() == self.closeval:
            return "closed"
        else:
            return "open"

    def open(self):
        count = 0
        while self.state.get() != self.openval:
            count += 1
            print("\u231b", end=" ", flush=True)
            yield from bps.mv(self.opn, 1)
            if count >= self.maxcount:
                print(
                    "tried %d times and failed to open %s %s" % (count, self.name, ":(")
                )  # u'\u2639'  unicode frown
                return (yield from bps.null())
            yield from bps.sleep(1.5)
        print("Opened {}".format(self.name))

    def close(self):
        count = 0
        while self.state.get() != self.closeval:
            count += 1
            print("\u231b", end=" ", flush=True)
            yield from bps.mv(self.cls, 1)
            if count >= self.maxcount:
                print(
                    "tried %d times and failed to close %s %s"
                    % (count, self.name, ":(")
                )
                return (yield from bps.null())
            yield from bps.sleep(1.5)
        print("Closed {}".format(self.name))

    def open_nonplan(self):
        self.read()
        if self.state.get() != self.openval:
            count = 0
            while self.state.get() != self.openval:
                count += 1
                print("\u231b", end=" ", flush=True)
                self.opn.set(1)
                if count >= self.maxcount:
                    print(
                        "tried %d times and failed to open %s %s"
                        % (count, self.name, ":(")
                    )
                    return
                time.sleep(1.5)
                self.read()
            print(" Opened {}".format(self.name))
        else:
            print("{} is open".format(self.name))

    def close_nonplan(self):
        self.read()
        if self.state.get() != self.closeval:
            count = 0
            while self.state.get() != self.closeval:
                count += 1
                print("\u231b", end=" ", flush=True)
                self.cls.set(1)
                if count >= self.maxcount:
                    print(
                        "tried %d times and failed to close %s %s"
                        % (count, self.name, ":(")
                    )
                    return
                time.sleep(1.5)
                self.read()
            print(" Closed {}".format(self.name))
        else:
            print("{} is closed".format(self.name))


class ShutterSet(PVPositionerPC):
    """
    Used for set of Diode box shutters
    """

    readback = Cpt(EpicsSignal, "-RB")
    setpoint = Cpt(EpicsSignal, "-SP")

    def set(self, value, *args, **kwargs):
        if value is None:
            saw_rise = False

            def watcher(*, old_value, value, **kwargs):
                nonlocal saw_rise
                if value == 1:
                    saw_rise = True
                    return False
                if value == 0 and saw_rise:
                    return True

            return SubscriptionStatus(self.readback, watcher)
        else:
            return super().set(value, *args, **kwargs)
