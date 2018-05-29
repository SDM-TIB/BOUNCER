#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages

setup(name='BOUNCER',
      version='1.0',
      description='BOUNCER - Privacy-aware Query Processing Over Federations of RDF Datasets',
      author='Kemele M. Endris',
      author_email='endris@L3s.de',
      url='https://github.com/SDM-TIB/BOUNCER',
      scripts=['start_experiment.py'],
      packages=find_packages(exclude=['docs']),
      install_requires=["ply", "flask", "networkx"],
      include_package_data=True,
      license='GNU/GPL v2'
     )
