# Pabot

[Русская версия](README_ru.md)
[中文版](README_zh.md)

[![Version](https://img.shields.io/pypi/v/robotframework-pabot.svg)](https://pypi.python.org/pypi/robotframework-pabot)
[![Downloads](http://pepy.tech/badge/robotframework-pabot)](http://pepy.tech/project/robotframework-pabot)
[![Build Status](https://travis-ci.org/mkorpela/pabot.svg?branch=master)](https://travis-ci.org/mkorpela/pabot)
[![Build status](https://ci.appveyor.com/api/projects/status/5g52rkflbtfw2anb/branch/master?svg=true)](https://ci.appveyor.com/project/mkorpela/pabot/branch/master)
[![Coverage](https://coveralls.io/repos/mkorpela/pabot/badge.svg)](https://coveralls.io/r/mkorpela/pabot)


<img src="https://raw.githubusercontent.com/mkorpela/pabot/master/pabot.png" width="100">

----

A parallel executor for [Robot Framework](http://www.robotframework.org) tests. With Pabot you can split one execution into multiple and save test execution time.

[![Pabot presentation at robocon.io 2018](http://img.youtube.com/vi/i0RV6SJSIn8/0.jpg)](https://youtu.be/i0RV6SJSIn8 "Pabot presentation at robocon.io 2018")

## Installation:

From PyPi:

     pip install -U robotframework-pabot

OR clone this repository and run:

     setup.py  install

## Basic use

Split execution to suite files.

     pabot [path to tests]

Split execution on test level.

     pabot --testlevelsplit [path to tests]

Run same tests with two different configurations.

     pabot --argumentfile1 first.args --argumentfile2 second.args [path to tests]

For more complex cases please read onward.

## Contact

Join [Pabot Slack channel](https://robotframework.slack.com/messages/C7HKR2L6L) in Robot Framework slack.
[Get invite to Robot Framework slack](https://robotframework-slack-invite.herokuapp.com/).


## Contributing to the project

There are several ways you can help in improving this tool:

   - Report an issue or an improvement idea to the [issue tracker](https://github.com/mkorpela/pabot/issues)
   - Contribute by programming and making a pull request (easiest way is to work on an issue from the issue tracker)

## Command-line options

    pabot [--verbose|--testlevelsplit|--command .. --end-command|
           --processes num|--pabotlib|--pabotlibhost host|--pabotlibport port|
           --artifacts extensions|--artifactsinsubfolders|
           --resourcefile file|--argumentfile[num] file|--suitesfrom file] 
          [robot options] [path ...]

Supports all [Robot Framework command line options](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#all-command-line-options) and also following options (these must be before RF options):

--verbose     
  more output from the parallel execution

--testlevelsplit          
  Split execution on test level instead of default suite level.
  If .pabotsuitenames contains both tests and suites then this
  will only affect new suites and split only them.
  Leaving this flag out when both suites and tests in
  .pabotsuitenames file will also only affect new suites and
  add them as suite files.

--command [ACTUAL COMMANDS TO START ROBOT EXECUTOR] --end-command    
  RF script for situations where robot is not used directly

--processes   [NUMBER OF PROCESSES]          
  How many parallel executors to use (default max of 2 and cpu count)

--pabotlib          
  Start PabotLib remote server. This enables locking and resource distribution between parallel test executions.

--pabotlibhost   [HOSTNAME]          
  Host name of the PabotLib remote server (default is 127.0.0.1)
  If used with --pabotlib option, will change the host listen address of the created remote server (see https://github.com/robotframework/PythonRemoteServer)
  If used without the --pabotlib option, will connect to already running instance of the PabotLib remote server in the given host. The remote server can be also started and executed separately from pabot instances:
  
      python -m pabot.pabotlib <path_to_resourcefile> <host> <port>
      python -m pabot.pabotlib resource.txt 192.168.1.123 8271
  
  This enables sharing a resource with multiple Robot Framework instances.

--pabotlibport   [PORT]          
  Port number of the PabotLib remote server (default is 8270)
  See --pabotlibhost for more information

--resourcefile   [FILEPATH]          
  Indicator for a file that can contain shared variables for distributing resources. This needs to be used together with pabotlib option. Resource file syntax is same as Windows ini files. Where a section is a shared set of variables.
  
--artifacts [FILE EXTENSIONS]   
  List of file extensions (comma separated).    
  Defines which files (screenshots, videos etc.) from separate reporting directories would be copied and included in a final report.   
  Possible links to copied files in RF log would be updated (only relative paths supported).   
  The default value is `png`.    
  Examples:

     --artifacts png,mp4,txt

--artifactsinsubfolders   
  Copy artifacts located not only directly in the RF output dir, but also in it's sub-folders.

--argumentfile[INTEGER]   [FILEPATH]          
  Run same suites with multiple [argumentfile](http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#argument-files) options.
  For example:

     --argumentfile1 arg1.txt --argumentfile2 arg2.txt

--suitesfrom   [FILEPATH TO OUTPUTXML]          
  Optionally read suites from output.xml file. Failed suites will run
  first and longer running ones will be executed before shorter ones.

Example usages:

     pabot test_directory
     pabot --exclude FOO directory_to_tests
     pabot --command java -jar robotframework.jar --end-command --include SMOKE tests
     pabot --processes 10 tests     
     pabot --pabotlibhost 192.168.1.123 --pabotlibport 8271 --processes 10 tests
     pabot --pabotlib --pabotlibhost 192.168.1.111 --pabotlibport 8272 --processes 10 tests
     pabot --artifacts png,mp4,txt --artifactsinsubfolders directory_to_tests

### PabotLib

pabot.PabotLib provides keywords that will help communication and data sharing between the executor processes.
These can be helpful when you must ensure that only one of the processes uses some piece of data or operates on some part of the system under test at a time.

PabotLib Docs are located at https://pabot.org/PabotLib.html.

### PabotLib example:

test.robot

      *** Settings ***
      Library    pabot.PabotLib
      
      *** Test Case ***
      Testing PabotLib
        Acquire Lock   MyLock
        Log   This part is critical section
        Release Lock   MyLock
        ${valuesetname}=    Acquire Value Set  admin-server
        ${host}=   Get Value From Set   host
        ${username}=     Get Value From Set   username
        ${password}=     Get Value From Set   password
        Log   Do something with the values (for example access host with username and password)
        Release Value Set
        Log   After value set release others can obtain the variable values

valueset.dat

      [Server1]
      tags=admin-server
      HOST=123.123.123.123
      USERNAME=user1
      PASSWORD=password1
      
      [Server2]
      tags=server
      HOST=121.121.121.121
      USERNAME=user2
      PASSWORD=password2

      [Server2]
      tags=admin-server
      HOST=222.222.222.222
      USERNAME=user3
      PASSWORD=password4


pabot call

      pabot --pabotlib --resourcefile valueset.dat test.robot

### Controlling execution order and level of parallelism

.pabotsuitenames file contains the list of suites that will be executed.
File is created during pabot execution if not already there.
The file is a cache that pabot uses when re-executing same tests to speed up processing. 
This file can be partially manually edited but easier option is to use ```--ordering FILENAME```.
First 4 rows contain information that should not be edited - pabot will edit these when something changes.
After this come the suite names. 

With ```--ordering FILENAME``` you can have a list that controls order also. The syntax is same as .pabotsuitenames file syntax but does not contain 4 hash rows that are present in .pabotsuitenames. 

There are four possibilities to influence the execution:

  * The order of suites can be changed.
  * If a directory (or a directory structure) should be executed sequentially, add the directory suite name to a row.
  * You can add a line with text `#WAIT` to force executor to wait until all previous suites have been executed.
  * You can group suites and tests together to same executor process by adding line `{` before the group and `}`after.

### Global variables

Pabot will insert following global variables to Robot Framework namespace. These are here to enable PabotLib functionality and for custom listeners etc. to get some information on the overall execution of pabot.

      PABOTQUEUEINDEX - this contains a unique index number for the execution. Indexes start from 0.
      PABOTLIBURI - this contains the URI for the running PabotLib server
      PABOTEXECUTIONPOOLID - this contains the pool id (an integer) for the current Robot Framework executor. This is helpful for example when visualizing the execution flow from your own listener.
      PABOTNUMBEROFPROCESSES - max number of concurrent processes that pabot may use in execution.
      CALLER_ID - a universally unique identifier for this execution.
 
