#!/usr/bin/env python

from distutils.core import setup
import os
from setuptools import find_packages

name = 'Mikko Korpela'
# I might be just a little bit too much afraid of those bots..
address = name.lower().replace(' ', '.')+chr(64)+'gmail.com'

setup(name='robotframework-pabot',
      version='0.2',
      description='Parallelizing test runner for Robot Framework',
      author=name,
      author_email=address,
      url='https://github.com/mkorpela/pabot',
      packages=find_packages(),
      scripts = [os.path.join('scripts', 'pabot'), os.path.join('scripts', 'pabot.bat')],
      install_requires = ['robotframework'])
