#!/bin/sh
set -e
source .venv/bin/activate
pip install -U robotframework
pip install pytest
pip install -e .
python -m pytest tests
deactivate
