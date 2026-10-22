#!/bin/sh
set -e
source .venv/bin/activate
pip install -U robotframework
pip install pytest
python setup.py sdist
pip install dist/*.tar.gz
python -m pytest -o addopts="" tests
deactivate
