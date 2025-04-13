#!/usr/bin/env python

from setuptools import setup
import os
import sys

# Add src to path so that version can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from pabot import __version__

setup(
    name="robotframework-pabot",
    version=__version__,
)
