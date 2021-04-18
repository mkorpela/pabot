#!/usr/bin/env python

import os
from setuptools import setup, find_packages

name = "Mikko Korpela"
# I might be just a little bit too much afraid of those bots..
address = name.lower().replace(" ", ".") + chr(64) + "gmail.com"

setup(
    name="robotframework-pabot",
    version="1.12",
    description="Parallel test runner for Robot Framework",
    long_description="A parallel executor for Robot Framework tests."
    " With Pabot you can split one execution into multiple and save test execution time.",
    author=name,
    author_email=address,
    url="https://pabot.org",
    download_url="https://pypi.python.org/pypi/robotframework-pabot",
    packages=find_packages(),
    classifiers=[
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: Apache Software License",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Robot Framework",
    ],
    entry_points={"console_scripts": ["pabot=pabot.pabot:main"]},
    license="Apache License, Version 2.0",
    install_requires=["robotframework", 'typing;python_version<"3.5"'],
    include_package_data=True,
)
