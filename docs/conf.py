"""Sphinx configuration for nbs-bl documentation."""

project = "NBS-BL"
copyright = "2024, NSLS-II"
author = "NSLS-II"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_rtd_theme",
    "myst_parser",  # For markdown support
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# HTML output options
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "ophyd": ("https://blueskyproject.io/ophyd/", None),
    "bluesky": ("https://blueskyproject.io/bluesky/", None),
}

# Napoleon settings
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True

# MyST settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
