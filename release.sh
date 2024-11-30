cd ..
git clone git@github.com:mkorpela/pabot.git pabotrelease
cd pabotrelease
python -m build
twine upload -r robotframework-pabot dist/*.*
