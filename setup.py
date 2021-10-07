from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().split()

setup(
    author="NIST Staff",
    author_email=None,
    description="Beamline utility functions",
    install_requires=requirements,
    name="bl_funcs",
    use_scm_version=True,
    packages=find_packages()
)
