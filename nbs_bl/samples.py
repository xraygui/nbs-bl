from .globalVars import GLOBAL_SAMPLES, GLOBAL_SELECTED
from .help import add_to_func_list


@add_to_func_list
def set_sample(sampleid, origin="center"):
    print(f"Setting sample to {sampleid}")
    sample_info = GLOBAL_SAMPLES.get(str(sampleid), {})
    GLOBAL_SELECTED.clear()
    GLOBAL_SELECTED["sample_id"] = sampleid
    GLOBAL_SELECTED["origin"] = origin
    GLOBAL_SELECTED.update(sample_info)


@add_to_func_list
def list_samples():
    """List the currently loaded samples"""

    print("Samples loaded in sampleholder")
    for sample_id, sample in GLOBAL_SAMPLES.items():
        print(f"{sample['name']}: id {sample_id}")


@add_to_func_list
def print_selected_sample():
    """Print info about the currently selected sample"""
    if GLOBAL_SELECTED.get("sample_id", None) is not None:
        print(f"Current sample id: {GLOBAL_SELECTED['sample_id']}")
        print(f"Current sample name: {GLOBAL_SELECTED.get('name', '')}")
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
