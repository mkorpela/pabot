# Tricks

Different approaches and common knowledge about solving how to do parallel testing.

### Cookbook example: How to use pabot to distribute testing to multiple remote machines

Basic idea: 

  - Run remote library servers on the remote machines
  - Use pabotlib with a resource file to share the IP addresses of the remote machines
  - On a suite setup and teardown use PabotLib.Aquire Value Set, Get Value From Set and PabotLib.Release Value Set to set a specific suite to be executed with a specific remote machine (for example set the host ip to a global variable and use it in the Remote library import)


