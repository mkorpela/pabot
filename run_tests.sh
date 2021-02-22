#!/bin/sh
set -e
source .venv/bin/activate
pip install nose
pip install mypy
pip install .
./devpy3.sh
mypy .
./devpy2.sh
mv pabot/py3 hiddenpy3
mypy pabot
mv hiddenpy3 pabot/py3
nosetests tests
deactivate
rm -rf .pabotenv
