# Getting Started with nbs-bl

This guide will help you set up a minimal working environment for nbs-bl using simulated devices.

## Prerequisites

1. **Python Environment**
   ```bash
   # Create and activate a new conda environment
   conda create -n nbs-env python=3.11
   conda activate nbs-env

   # Install basic requirements
   pip install bluesky ophyd databroker ipython
   ```

2. **IPython Profile**
   ```bash
   # Create a new IPython profile
   ipython profile create nbs
   ```

## Installation

1. **Install nbs packages**
   ```bash
   # Install core packages
   pip install git+https://github.com/xraygui/nbs-core.git
   pip install git+https://github.com/xraygui/nbs-bl.git
   ```

2. **Create Basic Configuration**

   Create `~/.ipython/profile_nbs/startup/00-startup.py`:
   ```python
   """
   Startup script for NBS beamline configuration.

   This script imports and runs the configuration loader to set up all devices 
   and plans.
   """

   from nbs_bl.configuration import load_and_configure_everything

   # Load all configured devices and plans
   load_and_configure_everything()
   ```

   Create `~/.ipython/profile_nbs/startup/beamline.toml`:
   ```toml
   [configuration]
   has_slits = false
   has_motorized_samples = false
   has_motorized_eref = false

   [detector_sets.default]
   primary = "main_detector"
   normalization = "i0"

   [settings]
   modules = ["nbs_bl.startup"]
   ```

   Create `~/.ipython/profile_nbs/startup/devices.toml`:
   ```toml

   [energy]
   _target = "ophyd.sim.SynAxis"
   name = "Energy"
   _group = "motors"
   _role = "energy"

   [sample_x]
   _target = "ophyd.sim.SynAxis"
   name = "Sample X"
   _group = "motors"

   [main_detector]
   _target = "ophyd.sim.SynSignal"
   name = "Main Detector"
   _group = "detectors"

   [i0]
   _target = "ophyd.sim.SynSignal"
   name = "I0"
   _group = "detectors"
   ```

## First Steps

1. **Start IPython**
   ```bash
   ipython --profile=nbs
   ```

2. **Verify Setup**
   ```python
   # Check that devices loaded correctly
   In [1]: beamline.sample_x
   Out[1]: SynAxis(prefix='', name='Sample X', read_attrs=['readback', 'setpoint'], configuration_attrs=['velocity', 'acceleration'])

   # List all available detectors and their status
   In [2]: list_detectors()
   Out[2]: 
   ┌─── detectors ─────────────────────────────────────────────────────────────┐
   │main_detector: Main Detector; active                                       │
   │i0: I0; active                                                             │
   └───────────────────────────────────────────────────────────────────────────┘

   # Move a motor
   In [3]: RE(mv(sample_x, 1.0))

   # Take measurements with all detectors
   # Note: Unlike basic Bluesky, nbs_count automatically reads all detectors
   # You don't need to specify a detector list
   In [4]: RE(nbs_count(5))
   ```

## Next Steps

1. **Add More Devices**
   - Add additional motors and detectors to `devices.toml`
   - Create device groups for common operations
   - Define roles for special devices

2. **Create Custom Scans**
   - Use built-in scan plans
   - Customize scan parameters
   - Create new scan plans

3. **Explore Features**
   - Sample management
   - Device groups
   - Plan configuration
   - GUI integration

## Common Issues

1. **Configuration Issues**
   - Validate TOML syntax
   - Check file paths
   - Verify module imports

2. **Scan Errors**
   - Check device readiness
   - Verify scan parameters
   - Review error messages

## Where to Go Next

- Read the [Overview](overview.md) for a deeper understanding
- Check the [Configuration Reference](configuration_reference.md)
- Explore the API documentation
- Try the tutorials

## Note

This guide uses simulated devices from `ophyd.sim`:
- `SynAxis`: A synthetic motor that can be moved and positioned
- `SynGauss`: A synthetic detector that produces a Gaussian signal based on a motor position
- `SynSignal`: A synthetic signal that produces random values

These devices allow you to test and develop without requiring an EPICS connection. For real beamline deployment, you would replace these with actual EPICS devices. 