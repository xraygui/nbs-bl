NSLS-II Beamline Support Library
==============================

The NSLS-II Beamline Support Library (nbs-bl) provides core functionality for beamline operation and control at NSLS-II.

Features
--------

* Beamline configuration management
* Device control and monitoring
* Scan plans and utilities
* Simulation capabilities

Getting Started
--------------

To install nbs-bl:

.. code-block:: bash

   pip install -e .

Documentation
------------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   overview
   configuration_reference
   api/index

Configuration
------------

The library uses TOML configuration files to define beamline devices and settings:

* :doc:`configuration_reference` - Detailed guide to configuring your beamline
* :download:`Beamline Template <template_beamline.toml>` - Template for beamline.toml
* :download:`Devices Template <template_devices.toml>` - Template for devices.toml

Development
----------

This project is part of the `xraygui <https://github.com/xraygui>`_ organization on GitHub. 