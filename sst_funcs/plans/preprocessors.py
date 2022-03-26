from bluesky.plan_stubs import open_run, close_run
from bluesky.utils import RunEngineControlException, make_decorator
from bluesky.preprocessors import contingency_wrapper


def run_return_wrapper(plan, *, md=None):
    """Enclose in 'open_run' and 'close_run' messages.

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    md : dict, optional
        metadata to be passed into the 'open_run' message
    """
    yield from open_run(md)

    def except_plan(e):
        if isinstance(e, RunEngineControlException):
            yield from close_run(exit_status=e.exit_status)
        else:
            yield from close_run(exit_status='fail', reason=str(e))

    return (yield from contingency_wrapper(plan,
                                           except_plan=except_plan,
                                           else_plan=close_run))


run_return_decorator = make_decorator(run_return_wrapper)
