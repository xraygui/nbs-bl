from .beamline import GLOBAL_BEAMLINE
from .help import add_to_func_list, add_to_plan_list
from nbs_bl.plans.plan_stubs import sampleholder_set_sample, sampleholder_move_sample


@add_to_plan_list
def set_sample(sample_id):
    """Set the current sample without moving the sample holder.

    Parameters
    ----------
    sample_id : str
        Identifier of the sample to select
    """
    yield from sampleholder_set_sample(GLOBAL_BEAMLINE.primary_sampleholder, sample_id)


@add_to_plan_list
def move_sample(sample_id, **position):
    """Move to a sample position and set it as the current sample.

    Parameters
    ----------
    sample_id : str
        Identifier of the sample to move to
    **position : dict
        Additional offset position parameters (x, y, r, etc.)
    """
    yield from sampleholder_move_sample(
        GLOBAL_BEAMLINE.primary_sampleholder, sample_id, **position
    )


@add_to_func_list
def load_samples(filename):
    """Load sample definitions from a file.

    Parameters
    ----------
    filename : str
        Path to the sample definition file
    """
    sampleholder = GLOBAL_BEAMLINE.primary_sampleholder
    sampleholder.load_sample_file(filename)


@add_to_func_list
def list_samples():
    """Print a list of all samples currently loaded in the sampleholder."""
    print("Samples loaded in sampleholder")
    for sample_id, sample in GLOBAL_BEAMLINE.primary_sampleholder.samples.items():
        print(f"{sample['name']}: id {sample_id}")


@add_to_func_list
def print_selected_sample():
    """Print information about the currently selected sample."""
    sample = GLOBAL_BEAMLINE.primary_sampleholder.current_sample
    if sample is not None:
        print(f"Current sample id: {sample['sample_id']}")
        print(f"Current sample name: {sample.get('name', '')}")
    else:
        print("No sample currently selected")


@add_to_func_list
def add_sample_absolute(name, sample_id, coordinates, description=None, **kwargs):
    """Add a sample at a set of absolute coordinates.

    Parameters
    ----------
    name : str
        Name of the sample
    sample_id : str
        Unique identifier for the sample
    coordinates : list
        List of coordinates for sample position
    description : str, optional
        Description of the sample
    **kwargs : dict
        Additional sample metadata
    """
    sample_id = str(sample_id)
    GLOBAL_BEAMLINE.primary_sampleholder.add_sample(
        name,
        sample_id,
        {"coordinates": coordinates},
        description=description,
        origin="absolute",
        **kwargs,
    )


@add_to_func_list
def add_current_position_as_sample(name, sample_id, description=None, **kwargs):
    """Add a sample at the current sampleholder position.

    Parameters
    ----------
    name : str
        Name of the sample
    sample_id : str
        Unique identifier for the sample
    description : str, optional
        Description of the sample
    **kwargs : dict
        Additional sample metadata
    """
    sample_id = str(sample_id)
    GLOBAL_BEAMLINE.primary_sampleholder.add_current_position_as_sample(
        name, sample_id, description=description, **kwargs
    )


@add_to_func_list
def clear_samples():
    """Remove all samples from the sampleholder."""
    GLOBAL_BEAMLINE.primary_sampleholder.clear_samples()


@add_to_func_list
def remove_sample(sample_id):
    """Remove a specific sample from the sampleholder.

    Parameters
    ----------
    sample_id : str
        Identifier of the sample to remove
    """
    GLOBAL_BEAMLINE.primary_sampleholder.remove_sample(sample_id)
