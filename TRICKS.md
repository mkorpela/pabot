# Tricks

Different approaches and common knowledge about solving how to do parallel testing. (Please contribute!)

### Speed profiling

Before you split your tests to multiple parallel test runs, please first check that you don't have easy optimization targets- if this hasn't been done before then it might be that you can have much more significant speed up boost from this than from parallelization. There are good ways of profiling where execution time is spend: https://bitbucket.org/robotframework/robottools/src/master/keywordtimes/ and bunch of others.
Also Python cProfiler is a valuable tool https://docs.python.org/2/library/profile.html .

### Cookbook example: How to use pabot to distribute testing to multiple remote machines

Basic idea: 

  - Run remote library servers on the remote machines
  - Use pabotlib with a resource file to share the IP addresses of the remote machines
  - On a suite setup and teardown use `pabot.PabotLib.Acquire Value Set`, `Get Value From Set` and `pabot.PabotLib.Release Value Set` to set a specific suite to be executed with a specific remote machine (for example set the host ip to a global variable and use it in the Remote library import)


