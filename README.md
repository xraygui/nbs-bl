# NSLS-II Beamline Support Library

A Python library for beamline operation and control at NSLS-II, providing configuration management, device control, and scan plans.

## Features

- TOML-based beamline configuration system
- Device control and monitoring
- Scan plans and utilities
- Simulation capabilities for offline testing
- Integration with Bluesky/Ophyd ecosystem

## Installation

```bash
# Clone the repository
git clone https://github.com/xraygui/nbs-bl.git
cd nbs-bl

# Install in development mode
pip install -e .
```

## Dependencies

- Python 3.8+
- Bluesky
- Ophyd
- NumPy
- nbs-core

## Documentation

Documentation is available at [https://nbs-bl.readthedocs.io](https://nbs-bl.readthedocs.io)

## Configuration

The library uses TOML configuration files to define beamline devices and settings:
- `beamline.toml`: General beamline configuration
- `devices.toml`: Device-specific configuration

See the [configuration reference](https://nbs-bl.readthedocs.io/configuration_reference.html) for detailed documentation.

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details. 