# Pabot

[![Version](https://img.shields.io/pypi/v/robotframework-pabot.svg)](https://pypi.python.org/pypi/robotframework-pabot)
[![Downloads](http://pepy.tech/badge/robotframework-pabot)](http://pepy.tech/project/robotframework-pabot)
[![Build Status](https://travis-ci.org/mkorpela/pabot.svg?branch=master)](https://travis-ci.org/mkorpela/pabot)
[![Build status](https://ci.appveyor.com/api/projects/status/5g52rkflbtfw2anb/branch/master?svg=true)](https://ci.appveyor.com/project/mkorpela/pabot/branch/master)


<img src="https://raw.githubusercontent.com/mkorpela/pabot/master/pabot.png" width="100">

----

[Robot Framework](http://www.robotframework.org)测试的并行执行程序。 使用Pabot，您可以将一个执行分成多个并节省测试执行时间。

## 安装

From PyPi:

     pip install -U robotframework-pabot

OR clone this repository and run:

     setup.py  install

## 你应该知道的事情

   - Pabot默认会从套件文件中拆分测试执行。 对于测试级别拆分使用```--testlevelsplit```标志。
   - 在一般情况下，当并行执行时，您不能指望没有设计为平行执行的测试，以便开箱即用。 例如，如果测试操作或使用相同的数据，您可能会遇到麻烦（一个测试套件登录到系统，而另一个测试套件记录相同的会话等）。 PabotLib可以帮助您解决这些并发问题。

## 为项目做贡献

There are several ways you can help in improving this tool:

   - Report an issue or an improvement idea to the [issue tracker](https://github.com/mkorpela/pabot/issues)
   - Contribute by programming and making a pull request (easiest way is to work on an issue from the issue tracker)

## 命令行选项

支持所有Robot Framework命令行选项以及以下选项（这些选项必须在普通RF选项之前）：

--verbose     
  来自并行执行的更多输出

--testlevelsplit          
  在测试级别而不是默认套件级别上拆分执行。
  如果.pabotsuitenames包含测试和套件，那么这个
  只会影响新套件并仅拆分它们。
  当套房和测试中都留下这个标志
  .pabotsuitenames文件也只会影响新的套件和
  将它们添加为套件文件。

--command [开始执行Robot Framework的实际命令] --end-command    
  Robot Framework脚本适用于不直接使用pybot的情况

--processes   [进程数]          
  要使用多少个并行执行程序（默认最大值为2和cpu计数）

--pabotlib          
  启动PabotLib远程服务器。 这样可以在并行测试执行之间进行锁定和资源分配。

--pabotlibhost   [HOSTNAME]          
  Host name of the PabotLib remote server (default is 127.0.0.1)
  If used with --pabotlib option, will change the host listen address of the created remote server (see https://github.com/robotframework/PythonRemoteServer)
  If used without the --pabotlib option, will connect to already running instance of the PabotLib remote server in the given host. The remote server can be also started and executed separately from pabot instances:
  
      python -m pabot.PabotLib <path_to_resourcefile> <host> <port>
      python -m pabot.PabotLib resource.txt 192.168.1.123 8271
  
  This enables sharing a resource with multiple Robot Framework instances.

--pabotlibport   [PORT]          
  Port number of the PabotLib remote server (default is 8270)
  See --pabotlibhost for more information

--resourcefile   [FILEPATH]          
  Indicator for a file that can contain shared variables for distributing resources. This needs to be used together with pabotlib option. Resource file syntax is same as Windows ini files. Where a section is a shared set of variables.

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

### PabotLib

pabot.PabotLib provides keywords that will help communication and data sharing between the executor processes.
These can be helpful when you must ensure that only one of the processes uses some piece of data or operates on some part of the system under test at a time.

Docs are located at https://cdn.rawgit.com/mkorpela/pabot/master/PabotLib.html

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
This file can be partially manually edited.
First 4 rows contain information that should not be edited - pabot will edit these when something changes.
After this come the suite names. 

There are three possibilities to influence the execution:

  * The order of suites can be changed.
  * If a directory (or a directory structure) should be executed sequentially, add the directory suite name to a row.
  * You can add a line with text `#WAIT` to force executor to wait until all previous suites have been executed.

### Global variables

Pabot will insert following global variables to Robot Framework namespace. These are here to enable PabotLib functionality and for custom listeners etc. to get some information on the overall execution of pabot.

      PABOTLIBURI - this contains the URI for the running PabotLib server
      PABOTEXECUTIONPOOLID - this contains the pool id (an integer) for the current Robot Framework executor. This is helpful for example when visualizing the execution flow from your own listener.
 