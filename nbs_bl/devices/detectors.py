from ophyd import Device, Component as Cpt, EpicsSignal, Signal
from ophyd.status import DeviceStatus
import threading
from queue import Queue, Empty
import time
import numpy as np


class ScalarBase(Device):
    exposure_time = Cpt(Signal, value=1, name="exposure_time", kind="config")
    mean = Cpt(Signal, name="", value=0, kind="hinted")
    median = Cpt(Signal, name="median", value=0, kind="omitted")
    std = Cpt(Signal, name="std", value=0, kind="omitted")
    npts = Cpt(Signal, name="points", value=0, kind="omitted")
    sum = Cpt(Signal, name="sum", value=0, kind="omitted")
    rescale = Cpt(Signal, value=1, name="rescale", kind="config")
    offset = Cpt(Signal, value=0, name="offset", kind="config")

    def __init__(self, *args, rescale=1, **kwargs):
        self._flying = False
        self._measuring = False
        self._reading = False
        self._flyer_buffer = []
        self._flyer_time_buffer = []
        super().__init__(*args, **kwargs)
        self.mean.name = self.name
        self.rescale.set(rescale).wait(timeout=60)

    def kickoff(self):
        self._flyer_buffer = []
        self._flyer_time_buffer = []
        self._flyer_timestamp_buffer = []
        self._flyer_queue = Queue()
        kickoff_st = DeviceStatus(device=self)
        kickoff_st.set_finished()
        self._flying = True
        if not self._measuring:
            self.target.subscribe(self._aggregate, run=False)
            self._measuring = True

        return kickoff_st

    def stage(self):
        self._secret_buffer = []
        self._secret_time_buffer = []
        self._buffer = []
        self._time_buffer = []
        self._reading = True
        if not self._measuring:
            self.target.subscribe(self._aggregate, run=False)
            self._measuring = True
        return super().stage()

    def unstage(self):
        if self._measuring:
            self.target.clear_sub(self._aggregate)
            self._measuring = False
        self._reading = False
        return super().unstage()

    def set_exposure(self, exp_time):
        self.exposure_time.set(exp_time).wait(timeout=60)

    def _aggregate(self, value, **kwargs):
        scale_value = value * self.rescale.get() - self.offset.get()
        t = time.time()
        if self._reading:
            self._buffer.append(scale_value)
            self._time_buffer.append(t)
        if self._flying:
            event = dict()
            event["time"] = t
            event["data"] = dict()
            event["timestamps"] = dict()
            event["data"][self.name] = scale_value
            event["timestamps"][self.name] = kwargs.get("timestamp", t)
            self._flyer_buffer.append(scale_value)
            self._flyer_time_buffer.append(t)
            self._flyer_timestamp_buffer.append(kwargs.get("timestamp", t))
            self._flyer_queue.put(event)

    def _acquire(self, status):
        self._buffer = []
        self._time_buffer = []
        time.sleep(self.exposure_time.get())
        if len(self._buffer) == 0:
            ntry = 10
            n = 0
            while len(self._buffer) < 1:
                time.sleep(0.1 * self.exposure_time.get())
                n += 1
                if n > ntry:
                    break
        buf = np.array(self._buffer)
        tbuf = np.array(self._time_buffer[: len(buf)])
        if len(buf) == 0:
            self.mean.put(np.nan)
            self.median.put(np.nan)
            self.std.put(np.nan)
            self.npts.put(0)
            self.sum.put(np.nan)

        else:
            self.mean.put(np.mean(buf))
            self.median.put(np.median(buf))
            self.std.put(np.std(buf))
            self.npts.put(len(buf))
            self.sum.put(np.sum(buf))
        self._secret_buffer.append(buf)
        self._secret_time_buffer.append(tbuf)
        status.set_finished()
        return

    def trigger(self):
        status = DeviceStatus(self)
        threading.Thread(target=self._acquire, args=(status,), daemon=True).start()
        return status

    def collect(self):
        events = []
        while True:
            try:
                e = self._flyer_queue.get_nowait()
                events.append(e)
            except Empty:
                break
        yield from events

    def complete(self):
        self._flying = False
        if self._measuring:
            self.target.clear_sub(self._aggregate)
            self._measuring = False
        completion_status = DeviceStatus(self)
        completion_status.set_finished()
        return completion_status

    def describe_collect(self):
        dd = dict(
            {self.name: {"source": self.target.pvname, "dtype": "number", "shape": []}}
        )
        return {self.name + "_monitor": dd}

    def get_plot_hints(self):
        return [self.mean.name]


class ophScalar(ScalarBase):
    """Generic Scalar.  Give full path to target PV during object creation"""

    target = Cpt(EpicsSignal, "", kind="omitted")
