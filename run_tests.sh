virtualenv -p /usr/bin/python3 .pabotenv
source .pabotenv/bin/activate
pip install nose
pip install .
nosetests tests
deactivate
rm -rf .pabotenv

