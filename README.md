Pabot
=====

A parallel executor for Robot Framework test cases.

Supports all Robot Framework command line options and also following options (these must be before normal RF options):

--verbose     
  more output

--command [ACTUAL COMMANDS TO START ROBOT EXECUTOR] --end-command    
  RF script for situations where pybot is not used directly

--processes   [NUMBER OF PROCESSES]          
  How many parallel executors to use (default max of 2 and cpu count)

Example usages:

     pabot test_directory
     pabot --exclude FOO directory_to_tests
     pabot --command java -jar robotframework.jar --end-command --include SMOKE tests
     pabot --processes 10 tests

Installation:

From PyPi:

     pip install -U robotframework-pabot

Clone this repository and run:

     setup.py  install
