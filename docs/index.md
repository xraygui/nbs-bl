# NSLS-II Beamline Support Library

The NSLS-II Beamline Support Library (nbs-bl) provides core functionality for beamline operation and control at NSLS-II. It includes:

- Beamline configuration management
- Device control and monitoring
- Scan plans and utilities
- Simulation capabilities

## Getting Started

To install nbs-bl:

```bash
pip install -e .
```

## Configuration

The library uses TOML configuration files to define beamline devices and settings:

- [Configuration Reference](configuration_reference.md) - Detailed guide to configuring your beamline
- [Beamline Template](template_beamline.toml) - Template for beamline.toml
- [Devices Template](template_devices.toml) - Template for devices.toml

## Development

This project is part of the [xraygui](https://github.com/xraygui) organization on GitHub. 