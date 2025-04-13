cd ..
git clone git@github.com:mkorpela/pabot.git pabotrelease
cd pabotrelease
pip install --upgrade pip build twine
python -m build
twine check dist/*
twine upload -r robotframework-pabot dist/*.*
