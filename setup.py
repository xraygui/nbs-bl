from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().split()

setup(
    author="Charles Titus",
    author_email="ctitus@bnl.gov",
    description="Beamline Framework",
    install_requires=requirements,
    use_scm_version=True,
    name="nbs-bl",
    packages=find_packages(),
)
