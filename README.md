# Pabot

[中文版](README_zh.md)

[![Version](https://img.shields.io/pypi/v/robotframework-pabot.svg)](https://pypi.python.org/pypi/robotframework-pabot)
[![Downloads](http://pepy.tech/badge/robotframework-pabot)](http://pepy.tech/project/robotframework-pabot)

<img src="https://raw.githubusercontent.com/mkorpela/pabot/master/pabot.png" width="100">

----

A parallel executor for [Robot Framework](http://www.robotframework.org) tests. With Pabot you can split one execution into multiple and save test execution time.

[![Pabot presentation at robocon.io 2018](http://img.youtube.com/vi/i0RV6SJSIn8/0.jpg)](https://youtu.be/i0RV6SJSIn8 "Pabot presentation at robocon.io 2018")

## Installation:

From PyPi:

     pip install -U robotframework-pabot

OR clone this repository and run:

     setup.py  install

OR clone this repository and run:

     pip install --editable .

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
<!-- START DOCSTRING -->
pabot [--verbose|--testlevelsplit|--command .. --end-command|
        --processes num|--no-pabotlib|--pabotlibhost host|--pabotlibport port|
        --processtimeout num|
        --shard i/n|
        --artifacts extensions|--artifactsinsubfolders|
        --resourcefile file|--argumentfile[num] file|--suitesfrom file|--ordering file|
        --chunk|
        --pabotprerunmodifier modifier|
        --no-rebot|
        --help|--version]
      [robot options] [path ...]

PabotLib remote server is started by default to enable locking and resource distribution between parallel test executions.

Supports all [Robot Framework command line options](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#all-command-line-options) and also following pabot options:

--verbose     
  More output from the parallel execution.

--testlevelsplit          
  Split execution on test level instead of default suite level. If .pabotsuitenames contains both tests and suites then
  this will only affect new suites and split only them. Leaving this flag out when both suites and tests in 
  .pabotsuitenames file will also only affect new suites and add them as suite files.

--command [ACTUAL COMMANDS TO START ROBOT EXECUTOR] --end-command    
  RF script for situations where robot is not used directly.

--processes [NUMBER OF PROCESSES]          
  How many parallel executors to use (default max of 2 and cpu count). Special option "all" will use as many processes as 
  there are executable suites or tests.

--no-pabotlib  
  Disable the PabotLib remote server if you don't need locking or resource distribution features.

--pabotlibhost [HOSTNAME]          
  Connect to an already running instance of the PabotLib remote server at the given host (disables the local PabotLib 
  server start). For example, to connect to a remote PabotLib server running on another machine:
  
      pabot --pabotlibhost 192.168.1.123 --pabotlibport 8271 tests/

  The remote server can be also started and executed separately from pabot instances:
  
      python -m pabot.pabotlib <path_to_resourcefile> <host> <port>
      python -m pabot.pabotlib resource.txt 192.168.1.123 8271
  
  This enables sharing a resource with multiple Robot Framework instances.

--pabotlibport [PORT]          
  Port number of the PabotLib remote server (default is 8270). See --pabotlibhost for more information.

--processtimeout [TIMEOUT]          
  Maximum time in seconds to wait for a process before killing it. If not set, there's no timeout.

--shard [INDEX]/[TOTAL]   
  Optionally split execution into smaller pieces. This can be used for distributing testing to multiple machines.
  
--artifacts [FILE EXTENSIONS]   
  List of file extensions (comma separated). Defines which files (screenshots, videos etc.) from separate reporting 
  directories would be copied and included in a final report. Possible links to copied files in RF log would be updated 
  (only relative paths supported). The default value is `png`.

  Examples:

     --artifacts png,mp4,txt

--artifactsinsubfolders   
  Copy artifacts located not only directly in the RF output dir, but also in it's sub-folders.

--resourcefile [FILEPATH]          
  Indicator for a file that can contain shared variables for distributing resources. This needs to be used together with 
  pabotlib option. Resource file syntax is same as Windows ini files. Where a section is a shared set of variables.

--argumentfile [INTEGER] [FILEPATH]          
  Run same suites with multiple [argumentfile](http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#argument-files) options.

  For example:

     --argumentfile1 arg1.txt --argumentfile2 arg2.txt

--suitesfrom [FILEPATH TO OUTPUTXML]          
  Optionally read suites from output.xml file. Failed suites will run first and longer running ones will be executed 
  before shorter ones.

--ordering [FILE PATH]   
  Optionally give execution order from a file.

--chunk   
  Optionally chunk tests to PROCESSES number of robot runs. This can save time because all the suites will share the same 
  setups and teardowns.

--pabotprerunmodifier [PRERUNMODIFIER MODULE OR CLASS]   
  Like Robot Framework's --prerunmodifier, but executed only once in the pabot's main process after all other 
  --prerunmodifiers. But unlike the regular --prerunmodifier command, --pabotprerunmodifier is not executed again in each 
  pabot subprocesses. Depending on the intended use, this may be desirable as well as more efficient. Can be used, for 
  example, to modify the list of tests to be performed.

--no-rebot    
  If specified, the tests will execute as usual, but Rebot will not be called to merge the logs. This option is designed 
  for scenarios where Rebot should be run later due to large log files, ensuring better memory and resource availability. 
  Subprocess results are stored in the pabot_results folder.

--help             
  Print usage instructions.
 
--version                
  Print version information.

Example usages:

     pabot test_directory
     pabot --exclude FOO directory_to_tests
     pabot --command java -jar robotframework.jar --end-command --include SMOKE tests
     pabot --processes 10 tests     
     pabot --pabotlibhost 192.168.1.123 --pabotlibport 8271 --processes 10 tests
     pabot --artifacts png,mp4,txt --artifactsinsubfolders directory_to_tests
     # To disable PabotLib:
     pabot --no-pabotlib tests

<!-- END DOCSTRING -->
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

      [Server3]
      tags=admin-server
      HOST=222.222.222.222
      USERNAME=user3
      PASSWORD=password4


pabot call using resources from valueset.dat

      pabot --pabotlib --resourcefile valueset.dat test.robot

### Controlling execution order and level of parallelism

.pabotsuitenames file contains the list of suites that will be executed.
File is created during pabot execution if not already there.
The file is a cache that pabot uses when re-executing same tests to speed up processing. 
This file can be partially manually edited but easier option is to use ```--ordering FILENAME```.
First 4 rows contain information that should not be edited - pabot will edit these when something changes.
After this come the suite names.

With ```--ordering FILENAME``` you can have a list that controls order also. The syntax is same as .pabotsuitenames file syntax but does not contain 4 hash rows that are present in .pabotsuitenames. 

There different possibilities to influence the execution:

  * The order of suites can be changed.
  * If a directory (or a directory structure) should be executed sequentially, add the directory suite name to a row as a ```--suite``` option.
  * If the base suite name is changing with robot option [```--name / -N```](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#setting-the-name) you can also give partial suite name without the base suite.
  * You can add a line with text `#WAIT` to force executor to wait until all previous suites have been executed.
  * You can group suites and tests together to same executor process by adding line `{` before the group and `}`after.
  * You can introduce dependencies using the word `#DEPENDS` after a test declaration. Can be used several times if it is necessary to refer to several different tests. Please take care that in case of circular dependencies an exception will be thrown. An example could be.

```
--test robotTest.1 Scalar.Test With Environment Variables #DEPENDS robotTest.1 Scalar.Test with BuiltIn Variables of Robot Framework
--test robotTest.1 Scalar.Test with BuiltIn Variables of Robot Framework
--test robotTest.2 Lists.Test with Keywords and a list
#WAIT
--test robotTest.2 Lists.Test with a Keyword that accepts multiple arguments
--test robotTest.2 Lists.Test with some Collections keywords
--test robotTest.2 Lists.Test to access list entries
--test robotTest.3 Dictionary.Test that accesses Dictionaries
--test robotTest.3 Dictionary.Dictionaries for named arguments #DEPENDS robotTest.3 Dictionary.Test that accesses Dictionaries
--test robotTest.1 Scalar.Test Case With Variables #DEPENDS robotTest.3 Dictionary.Test that accesses Dictionaries
--test robotTest.1 Scalar.Test with Numbers #DEPENDS robotTest.1 Scalar.Test With Arguments and Return Values
--test robotTest.1 Scalar.Test Case with Return Values #DEPENDS robotTest.1 Scalar.Test with Numbers
--test robotTest.1 Scalar.Test With Arguments and Return Values
--test robotTest.3 Dictionary.Test with Dictionaries as Arguments
--test robotTest.3 Dictionary.Test with FOR loops and Dictionaries #DEPENDS robotTest.1 Scalar.Test Case with Return Values
```

  * By using the command `#SLEEP X`, where `X` is an integer in the range [0-3600] (in seconds), you can 
  define a startup delay for each subprocess. `#SLEEP` affects the next line unless the next line starts a 
  group with `{`, in which case the delay applies to the entire group. If the next line begins with `--test` 
  or `--suite`, the delay is applied to that specific item. Any other occurrences of `#SLEEP` are ignored.

The following example clarifies the behavior:

```sh
pabot --process 2 --ordering order.txt data_1
```

where order.txt is:

```
#SLEEP 1
{
#SLEEP 2
--suite Data 1.suite A
#SLEEP 3
--suite Data 1.suite B
#SLEEP 4
}
#SLEEP 5
#SLEEP 6
--suite Data 1.suite C
#SLEEP 7
--suite Data 1.suite D
#SLEEP 8
```

prints something like this:

```
2025-02-15 19:15:00.408321 [0] [ID:1] SLEEPING 6 SECONDS BEFORE STARTING Data 1.suite C
2025-02-15 19:15:00.408321 [1] [ID:0] SLEEPING 1 SECONDS BEFORE STARTING Group_Data 1.suite A_Data 1.suite B
2025-02-15 19:15:01.409389 [PID:52008] [1] [ID:0] EXECUTING Group_Data 1.suite A_Data 1.suite B
2025-02-15 19:15:06.409024 [PID:1528] [0] [ID:1] EXECUTING Data 1.suite C
2025-02-15 19:15:09.257564 [PID:52008] [1] [ID:0] PASSED Group_Data 1.suite A_Data 1.suite B in 7.8 seconds
2025-02-15 19:15:09.259067 [1] [ID:2] SLEEPING 7 SECONDS BEFORE STARTING Data 1.suite D
2025-02-15 19:15:09.647342 [PID:1528] [0] [ID:1] PASSED Data 1.suite C in 3.2 seconds
2025-02-15 19:15:16.260432 [PID:48156] [1] [ID:2] EXECUTING Data 1.suite D
2025-02-15 19:15:18.696420 [PID:48156] [1] [ID:2] PASSED Data 1.suite D in 2.4 seconds
```

### Programmatic use

Library offers an endpoint `main_program` that will not call `sys.exit`. This can help in developing your own python program around pabot.

```Python
import sys
from pabot.pabot import main_program

def amazing_new_program():
    print("Before calling pabot")
    exit_code = main_program(['tests'])
    print(f"After calling pabot (return code {exit_code})")
    sys.exit(exit_code)

```

### Global variables

Pabot will insert following global variables to Robot Framework namespace. These are here to enable PabotLib functionality and for custom listeners etc. to get some information on the overall execution of pabot.

      PABOTQUEUEINDEX - this contains a unique index number for the execution. Indexes start from 0.
      PABOTLIBURI - this contains the URI for the running PabotLib server
      PABOTEXECUTIONPOOLID - this contains the pool id (an integer) for the current Robot Framework executor. This is helpful for example when visualizing the execution flow from your own listener.
      PABOTNUMBEROFPROCESSES - max number of concurrent processes that pabot may use in execution.
      CALLER_ID - a universally unique identifier for this execution.
 
