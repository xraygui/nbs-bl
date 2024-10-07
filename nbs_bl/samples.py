from .beamline import GLOBAL_BEAMLINE
from .help import add_to_func_list, add_to_plan_list
from nbs_bl.plans.plan_stubs import sampleholder_set_sample, sampleholder_move_sample


@add_to_plan_list
def set_sample(sample_id):
    yield from sampleholder_set_sample(GLOBAL_BEAMLINE.primary_sampleholder, sample_id)


@add_to_plan_list
def move_sample(sample_id, **position):
    yield from sampleholder_move_sample(
        GLOBAL_BEAMLINE.primary_sampleholder, sample_id, **position
    )


@add_to_func_list
def load_samples(filename):
    sampleholder = GLOBAL_BEAMLINE.primary_sampleholder
    sampleholder.load_sample_file(filename)


@add_to_func_list
def list_samples():
    """List the currently loaded samples"""

    print("Samples loaded in sampleholder")
    for sample_id, sample in GLOBAL_BEAMLINE.primary_sampleholder.samples.items():
        print(f"{sample['name']}: id {sample_id}")


@add_to_func_list
def print_selected_sample():
    """Print info about the currently selected sample"""
    sample = GLOBAL_BEAMLINE.primary_sampleholder.current_sample
    if sample is not None:
        print(f"Current sample id: {sample['sample_id']}")
        print(f"Current sample name: {sample.get('name', '')}")
    else:
        print(f"No sample currently selected")


@add_to_func_list
def add_sample_to_globals(
    sample_id, name, position, side, thickness, description=None, **kwargs
):
    sample_id = str(sample_id)
    GLOBAL_SAMPLES[sample_id] = {
        "name": name,
        "position": position,
        "side": side,
        "thickness": thickness,
        "description": description,
        **kwargs,
    }


@add_to_func_list
def clear_samples():
    GLOBAL_BEAMLINE.primary_sampleholder.clear_samples()


@add_to_func_list
def remove_sample(sample_id):
    GLOBAL_BEAMLINE.primary_sampleholder.remove_sample(sample_id)
