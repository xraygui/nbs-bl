from ..utils import merge_func
from importlib.metadata import entry_points
from bluesky.preprocessors import finalize_wrapper
from bluesky.suspenders import SuspenderBase
from bluesky import Msg
from ..beamline import GLOBAL_BEAMLINE


def get_suspender_entrypoints():
    """
    Get suspender entrypoints from beamline configuration.

    Returns
    -------
    list
        List of decorator functions loaded from entrypoints
    """
    config = GLOBAL_BEAMLINE.config
    suspender_entrypoints = config.get("settings", {}).get("suspenders", [])
    print(f"Suspender entrypoints: {suspender_entrypoints}")
    suspenders = []
    if suspender_entrypoints:
        eps = entry_points()

        for ep_name in suspender_entrypoints:
            try:
                # Look for entrypoint in nbs_bl.suspenders group
                matches = eps.select(group="nbs_bl.suspenders", name=ep_name)
                for match in matches:
                    print(f"Loading suspender {match.name}")
                    suspender = match.load()

                    # Handle both single suspender and list of suspenders
                    if isinstance(suspender, (list, tuple)):
                        suspenders.extend(suspender)
                    else:
                        suspenders.append(suspender)
            except Exception as e:
                print(f"Failed to load suspender {ep_name}: {e}")

    return suspenders


def dynamic_suspenders(func):
    # Load suspenders from entrypoints at decoration time
    suspenders = get_suspender_entrypoints()

    @merge_func(func)
    def wrapper(*args, skip_suspenders=False, **kwargs):
        """
        Parameters
        ----------
        skip_suspenders : bool, optional
            If True, do not install suspenders
        """
        # Check if suspenders should be skipped

        if skip_suspenders or not suspenders:
            return (yield from func(*args, **kwargs))
        else:
            suspender_list = []
            for sus in suspenders:
                if callable(sus) and not isinstance(sus, SuspenderBase):
                    sus = sus()
                if isinstance(sus, (list, tuple)):
                    suspender_list.extend(sus)
                else:
                    suspender_list.append(sus)

            def _install():
                for susp in suspender_list:
                    yield Msg("install_suspender", None, susp)

            def _remove():
                for susp in suspender_list:
                    yield Msg("remove_suspender", None, susp)

            @merge_func(func)
            def _inner_plan(*args, **kwargs):
                yield from _install()
                return (yield from func(*args, **kwargs))

            return (
                yield from finalize_wrapper(_inner_plan(*args, **kwargs), _remove())
            )

    return wrapper
