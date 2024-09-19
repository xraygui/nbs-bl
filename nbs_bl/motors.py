from ophyd.utils.errors import DisconnectedError
from .globalVars import GLOBAL_BEAMLINE
from .help import add_to_func_list
from queue import Queue, Empty
import time
import threading

from ophyd import EpicsMotor, Signal, PositionerBase, Device
from ophyd.pv_positioner import PVPositioner
from ophyd import Component as Cpt
from ophyd.status import wait as status_wait, DeviceStatus


@add_to_func_list
def list_motors(verbose=False):
    """List the most important motors and their current positions"""

    def textFunction(key, device):
        name = device.name
        try:
            position = device.position
        except DisconnectedError:
            position = "disconnected"
        text = f"{name}: {position}"
        return text

    GLOBAL_BEAMLINE.motors.describe(verbose, textFunction)


class FlyerMixin:

    def __init__(self, *args, **kwargs):
        self._ready_to_fly = False
        self._fly_move_st = None
        self._default_time_resolution = 0.1
        self._time_resolution = None
        super().__init__(*args, **kwargs)

    # Flyer motor methods
    def preflight(self, start, stop, speed=None, time_resolution=None):
        self._old_velocity = self.velocity.get()
        self._flyer_stop = stop
        st = self.move(start)
        if speed is None:
            speed = self._old_velocity
        self.velocity.set(speed)
        if time_resolution is not None:
            self._time_resolution = time_resolution
        else:
            self._time_resolution = self._default_time_resolution
        self._last_readback_value = start
        self._ready_to_fly = True
        return st

    def fly(self):
        """
        Should be called after all detectors start flying, so that we don't lose data
        """
        if not self._ready_to_fly:
            self._fly_move_st = DeviceStatus(device=self)
            self._fly_move_st.set_finished(success=False)
        else:
            self._fly_move_st = self.move(self._flyer_stop, wait=False)
            self._flying = True
            self._ready_to_fly = False
        return self._fly_move_st

    def land(self):
        if self._fly_move_st.done:
            self.velocity.set(self._old_velocity)
            self._flying = False
            self._time_resolution = None

    # Flyer detector methods for readback
    def kickoff(self):
        kickoff_st = DeviceStatus(device=self)
        self._flyer_queue = Queue()
        self._measuring = True
        self._flyer_buffer = []
        threading.Thread(target=self._aggregate, daemon=True).start()
        # self.user_readback.subscribe(self._aggregate, run=False)
        kickoff_st.set_finished()
        return kickoff_st

    def _aggregate(self):
        name = self.user_readback.name
        while self._measuring:
            t = time.time()
            rb = self.user_readback.read()
            value = rb[name]["value"]
            ts = rb[name]["timestamp"]
            self._flyer_buffer.append(value)
            event = dict()
            event["time"] = t
            event["data"] = dict()
            event["timestamps"] = dict()
            event["data"][name] = value
            event["timestamps"][name] = ts
            self._flyer_queue.put(event)
            time.sleep(self._time_resolution)
        return

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
        if self._measuring:
            # self.user_readback.clear_sub(self._aggregate)
            self._measuring = False
        completion_status = DeviceStatus(self)
        completion_status.set_finished()
        self._time_resolution = None
        return completion_status

    def describe_collect(self):
        dd = dict(
            {
                self.user_readback.name: {
                    "source": self.user_readback.pvname,
                    "dtype": "number",
                    "shape": [],
                }
            }
        )
        return {self.name + "_monitor": dd}


class DeadbandMixin(Device, PositionerBase):
    """
    Should be the leftmost class in the inheritance list so that it grabs move first!

    Must be combined with either EpicsMotor or PVPositioner, or some other class
    that has a done_value attribute

    An EpicsMotor subclass that has an absolute tolerance for moves.
    If the readback is within tolerance of the setpoint, the MoveStatus
    is marked as finished, even if the motor is still settling.

    This prevents motors with long, but irrelevant, settling times from
    adding overhead to scans.
    """

    tolerance = Cpt(Signal, value=-1, kind="config")
    move_latch = Cpt(Signal, value=0, kind="omitted")

    def _done_moving(self, success=True, timestamp=None, value=None, **kwargs):
        """Call when motion has completed.  Runs ``SUB_DONE`` subscription."""
        if self.move_latch.get():
            # print(f"{timestamp}: {self.name} marked done")
            if success:
                self._run_subs(sub_type=self.SUB_DONE, timestamp=timestamp, value=value)

            self._run_subs(
                sub_type=self._SUB_REQ_DONE, success=success, timestamp=timestamp
            )
            self._reset_sub(self._SUB_REQ_DONE)
            self.move_latch.put(0)

    def move(self, position, wait=True, **kwargs):
        tolerance = self.tolerance.get()

        if tolerance < 0:
            self.move_latch.put(1)
            return super().move(position, wait=wait, **kwargs)
        else:
            status = super().move(position, wait=False, **kwargs)
            setpoint = position
            done_value = getattr(self, "done_value", 1)

            def check_deadband(value, timestamp, **kwargs):
                if abs(value - setpoint) < tolerance:
                    self._done_moving(
                        timestamp=timestamp, success=True, value=done_value
                    )
                else:
                    pass
                    # print(f"{timestamp}: {self.name}, {value} not within {tolerance} of {setpoint}")

            def clear_deadband(*args, **kwargs):
                # print(f"{timestamp}: Ran deadband clear for {self.name}")
                self.clear_sub(check_deadband, event_type=self.SUB_READBACK)

            self.subscribe(clear_deadband, event_type=self._SUB_REQ_DONE, run=False)
            self.move_latch.put(1)
            self.subscribe(check_deadband, event_type=self.SUB_READBACK, run=True)

            try:
                if wait:
                    status_wait(status)
            except KeyboardInterrupt:
                self.stop()
                raise

            return status


class DeadbandEpicsMotor(DeadbandMixin, EpicsMotor):
    """
    An EpicsMotor subclass that has an absolute tolerance for moves.
    If the readback is within tolerance of the setpoint, the MoveStatus
    is marked as finished, even if the motor is still settling.

    This prevents motors with long, but irrelevant, settling times from
    adding overhead to scans.

    This class is designed to be subclassed.
    """

    pass


class DeadbandPVPositioner(DeadbandMixin, PVPositioner):
    """
    A PVPositioner subclass that has an absolute tolerance for moves.
    If the readback is within tolerance of the setpoint, the MoveStatus
    is marked as finished, even if the motor is still settling.

    This prevents motors with long, but irrelevant, settling times from
    adding overhead to scans.

    This class is designed to be subclassed.
    """

    pass
