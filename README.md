Pabot
=====

Proof of consept parallel executor for Robot Framework test cases.

Command line options:
--verbose     more output
--command [ACTUAL COMMANDS] --end-command    RF script
--processes   [NUMBER OF PROCESSES]          How many parallel executors to use (default max of 2 and cpu count)

Example usages:
     ./pabot.py testit
     ./pabot.py --exclude FOO directory_to_tests
     ./pabot.py --command java -jar robotframework.jar --end-command --include SMOKE tests
     ./pabot.py --processes 10 testit
