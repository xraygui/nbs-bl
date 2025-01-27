# Overview of nbs-bl

## What is nbs-bl?

nbs-bl is a toolkit for creating beamline control packages at NSLS-II. It provides a foundation of standard functionality while allowing for beamline-specific customization. The library emphasizes configuration-driven development, separating the definition of beamline components from their implementation.

## Beamline Components

A working beamline consists of three main components:

1. **IPython Profile**
   - Contains multiple configuration files
   - Defines the beamline's startup behavior
   - Loads necessary modules and configurations

2. **Beamline Package**
   - Contains beamline-specific Python code
   - Implements custom device classes
   - Defines specialized scan plans
   - Provides startup routines

3. **EPICS Layer**
   - Collection of Process Variables (PVs)
   - Can connect to real hardware
   - Can connect to simulated hardware
   - Provides the interface between software and hardware

## Core Functionality

### 1. Configuration Management

nbs-bl provides a robust configuration system that:
- Loads objects from TOML configuration files
- Separates device definitions from implementation
- Allows for easy modification without code changes
- Supports environment-specific configurations

### 2. Plan Management

The library includes a plan loading system that:
- Loads scan definitions from configuration files
- Provides standard metadata handling
- Enables consistent plan execution
- Allows for plan customization

### 3. Device Organization

Devices are organized through:
- **Groups**: Collections of related devices (e.g., motors, detectors)
- **Roles**: Special labels that persist even when hardware changes
- Flexible hierarchy for device management
- Standard interfaces for device types

### 4. Built-in Features

The library provides built-in functionality for:
- Sample metadata management
- Sample movement and positioning
- Common scan metadata handling
- GUI communication methods
- Standard device classes and plans

### 5. GUI Integration

nbs-bl includes:
- Methods for GUI communication
- Standard interfaces for device control
- Support for real-time updates
- Integration with nbs-gui framework

## Ecosystem Integration

nbs-bl is part of a larger ecosystem:

1. **nbs-core**
   - Provides common utilities
   - Defines base classes
   - Implements shared functionality

2. **nbs-gui**
   - Creates graphical interfaces
   - Provides real-time monitoring
   - Enables user interaction

3. **nbs-sim**
   - Simulates beamline hardware
   - Enables offline testing
   - Supports development

4. **nbs-pods**
   - Manages deployment
   - Handles container orchestration
   - Provides consistent environments

## Key Advantages

1. **Configuration-Driven Development**
   - Separates configuration from code
   - Makes changes easier and safer
   - Reduces need for code modifications
   - Improves maintainability

2. **Standardization**
   - Common device classes
   - Standard scan patterns
   - Consistent interfaces
   - Shared best practices

3. **Flexibility**
   - Supports customization
   - Allows for beamline-specific needs
   - Extensible architecture
   - Modular design

4. **Integration**
   - Works with existing tools
   - Supports GUI development
   - Enables simulation
   - Facilitates deployment

## Use Cases

nbs-bl is ideal for:
- Setting up new beamlines
- Standardizing beamline control
- Implementing common functionality
- Creating maintainable systems
- Developing user interfaces
- Testing and simulation 