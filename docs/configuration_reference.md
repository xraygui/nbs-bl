# Beamline Configuration Reference

## Overview
The beamline configuration system uses TOML files to define the hardware, settings, and behavior of a beamline. The configuration is split into two main files:
- `beamline.toml`: Core beamline settings and capabilities
- `devices.toml`: Hardware device definitions and properties

## beamline.toml Reference

### Configuration Section
```toml
[configuration]
# List of devices to include in baseline readings
baseline = ["motor1", "detector1"]

# Core beamline capabilities
has_slits = true          # Whether beamline has slit devices
has_motorized_samples = true    # Whether beamline has motorized sample stages
has_motorized_eref = false     # Whether beamline has motorized energy reference
has_polarization = false       # Whether beamline has polarization control
```

### Detector Sets
Define groups of detectors that are commonly used together.
```toml
[detector_sets.default]
primary = "main_detector"        # Primary detector for measurements
normalization = "i0"            # Detector used for normalization
reference = "ir"                # Reference detector

[detector_sets.transmission]
primary = "it"
normalization = "i0"
reference = "ir"
```

### Settings
General beamline settings and module configuration.
```toml
[settings]
# Python modules to load at startup
modules = ["haxpes.startup", "rsoxs.startup"]

# Plan-specific settings
[settings.plans]
scan_plans = ["plans/xas.toml", "plans/xps.toml"]
alignment = ["plans/alignment.toml"]

# Redis metadata configuration
[settings.redis.md]
host = "redis"
prefix = "beamline_name"

# Redis info configuration
[settings.redis.info]
host = "redisInfo"
prefix = ""
port = 60737
db = 4
```

## devices.toml Reference

### Device Configuration Format
Each device entry follows this general structure:
```toml
[device_name]
# Required fields
_target = "package.module.DeviceClass"  # Python class to instantiate
name = "human_readable_name"            # Display name
prefix = "PV:PREFIX:"                   # EPICS PV prefix

# Optional fields
_defer_loading = false                  # Whether to defer device loading
_add_to_ns = true                       # Add to IPython namespace
description = "Device description"      # Human-readable description

# Group membership
groups = ["motors", "detectors"]        # Device groups
roles = ["primary_detector"]            # Device roles

# Device-specific parameters
param1 = value1
param2 = value2
```

### Common Device Types

#### Motors
```toml
[sample_x]
_target = "nbs_bl.devices.motors.DeadbandEpicsMotor"
name = "Sample X"
prefix = "MOTOR:X:"
groups = ["motors", "sample_motors"]
tolerance = 0.1
baseline = true
```

#### Detectors
```toml
[main_detector]
_target = "nbs_bl.devices.detectors.ophScalar"
name = "Main Detector"
prefix = "DET:MAIN:"
groups = ["detectors"]
roles = ["primary"]
description = "Main measurement detector"
rescale = 1.0
```

#### Sample Holders
```toml
[sample_holder]
_target = "nbs_bl.devices.sampleholders.Manipulator4AxBase"
name = "Sample Manipulator"
prefix = "MANIP:"
attachment_point = [0, 0, 0]
beam_direction = [0, -1, 0]
rotation_ax = 2
groups = ["manipulators"]
```

#### Shutters
```toml
[photon_shutter]
_target = "nbs_bl.devices.shutters.EPS_Shutter"
name = "Photon Shutter"
prefix = "PS:"
groups = ["shutters"]
openval = 1
closeval = 0
```

## Best Practices

### Device Organization
1. Group related devices together in the configuration
2. Use consistent naming conventions:
   - Lowercase with underscores for device keys
   - Descriptive human-readable names
   - Clear, consistent PV prefixes
3. Document special requirements or dependencies

### Deferred Loading
Use `_defer_loading = true` for devices that:
- Are not always available
- Have long initialization times
- Are only needed for specific operations
- May conflict with other devices

### Device Groups
Standard group names include:
- `motors`: All motor devices
- `detectors`: All detector devices
- `shutters`: Beam and safety shutters
- `gauges`: Vacuum gauges
- `manipulators`: Sample manipulation devices
- `mirrors`: Beamline optics
- `slits`: Beam-defining slits

### Device Roles
Common roles include:
- `beam_current`: Storage ring current measurement
- `beam_status`: Beam availability status
- `default_shutter`: Primary photon shutter
- `energy`: Monochromator or energy setting device
- `intensity_detector`: Primary intensity measurement
- `primary_sampleholder`: Main sample manipulation stage
- `reference_sampleholder`: Reference sample stage
- `slits`: Primary beam-defining slits

### Redis Configuration
1. Use separate configurations for metadata and info
2. Choose meaningful prefixes to avoid conflicts
3. Document required Redis setup and connectivity

## Configuration Validation
Before deploying a new configuration:
1. Verify all required fields are present
2. Check PV connectivity
3. Test device initialization
4. Validate group and role assignments
5. Ensure Redis connectivity
6. Test deferred loading behavior

## Common Issues and Solutions

### Device Loading Failures
- Verify PV prefix is correct
- Check EPICS IOC is running
- Ensure network connectivity
- Verify required dependencies are installed

### Redis Connectivity
- Check Redis server is running
- Verify port and host settings
- Ensure network allows Redis connections
- Check database permissions

### Group and Role Conflicts
- Verify no duplicate role assignments
- Check group membership logic
- Validate device compatibility
- Test interaction between grouped devices
``` 