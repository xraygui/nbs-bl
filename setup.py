from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().split()
    
setup(
    author="NIST Staff",
    author_email=None,
    description="Beamline hardware classes",
    install_requires=requirements,
    name="bl_base",
    use_scm_version=True,
    packages=find_packages()
)
