from ophyd import Device


class DummyObject(Device):
    """
    A dummy device that creates child DummyObjects on attribute access.

    Parameters
    ----------
    name : str
        Name of the dummy device

    Examples
    --------
    >>> manip = DummyObject(name="Manipulator")
    >>> manip.x  # Returns DummyObject named "Manipulator_x"
    >>> manip.x.readback  # Returns DummyObject named "Manipulator_x_readback"
    """

    def __init__(self, *args, name, **kwargs):
        super().__init__(*args, name=name)
        self._dummy_children = {}

    def __getattr__(self, attr):
        """Create and return a new DummyObject when an unknown attribute is accessed."""
        if attr.startswith("_"):
            return super().__getattr__(attr)

        # Create child name by appending the attribute
        child_name = f"{self.name}_{attr}"

        # Cache child objects to return the same instance on subsequent access
        if child_name not in self._dummy_children:
            self._dummy_children[child_name] = DummyObject(name=child_name)

        return self._dummy_children[child_name]
