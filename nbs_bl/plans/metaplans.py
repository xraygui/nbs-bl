import time
import typing
from ..help import add_to_plan_list

from bluesky_queueserver import parameter_annotation_decorator


@add_to_plan_list
@parameter_annotation_decorator(
    {
        "parameters": {
            "plans": {
                "annotation": "typing.List[__PLAN__]",
                "description": "List of plan names or callables to run in sequence.",
            }
        }
    }
)
def repeat_plan_sequence_for_duration(
    plans,
    plan_args_list: typing.List[typing.List],
    plan_kwargs_list: typing.List[typing.Dict],
    duration: float,
):
    """
    Repeat a sequence of plans for a specified duration.

    Parameters
    ----------
    plans : list of str or callables
        List of plan names (or callables) to run in sequence.
    plan_args_list : list of list
        List of argument lists, one for each plan.
    plan_kwargs_list : list of dict
        List of kwargs dicts, one for each plan.
    duration : float
        Total duration to repeat the sequence (seconds).

    Yields
    ------
    Msg
        Bluesky messages from the repeated plans.
    """
    start_time = time.time()
    n_plans = len(plans)
    idx = 0
    while (time.time() - start_time) < duration:
        plan = plans[idx % n_plans]
        args = plan_args_list[idx % n_plans]
        kwargs = plan_kwargs_list[idx % n_plans]
        yield from plan(*args, **kwargs)
        idx += 1


@add_to_plan_list
@parameter_annotation_decorator(
    {
        "parameters": {
            "plans": {
                "annotation": "typing.List[__PLAN__]",
                "description": "List of plan names or callables to run in sequence.",
            },
            "condition": {
                "annotation": "__PLAN__",
                "description": "A plan that returns a boolean; controls loop continuation.",
            },
        }
    }
)
def repeat_plan_sequence_while_condition(
    plans,
    plan_args_list: typing.List[typing.List],
    plan_kwargs_list: typing.List[typing.Dict],
    condition,
    condition_args: typing.List = None,
    condition_kwargs: typing.Dict = None,
):
    """
    Repeat a sequence of plans while a condition plan returns True.

    Parameters
    ----------
    plans : list of str or callables
        List of plan names (or callables) to run in sequence.
    plan_args_list : list of list
        List of argument lists, one for each plan.
    plan_kwargs_list : list of dict
        List of kwargs dicts, one for each plan.
    condition : str or callable
        A plan that returns a boolean; controls loop continuation.
    condition_args : list, optional
        Arguments for the condition plan.
    condition_kwargs : dict, optional
        Keyword arguments for the condition plan.

    Yields
    ------
    Msg
        Bluesky messages from the repeated plans.
    """
    n_plans = len(plans)
    idx = 0
    if condition_args is None:
        condition_args = []
    if condition_kwargs is None:
        condition_kwargs = {}
    while True:
        val = yield from condition(*condition_args, **condition_kwargs)
        if not val:
            break
        plan = plans[idx % n_plans]
        args = plan_args_list[idx % n_plans]
        kwargs = plan_kwargs_list[idx % n_plans]
        yield from plan(*args, **kwargs)
        idx += 1
