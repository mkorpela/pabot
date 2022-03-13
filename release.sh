cd ..
git clone git@github.com:mkorpela/pabot.git pabotrelease
cd pabotrelease
python setup.py sdist
twine upload -r robotframework-pabot dist/*.*
