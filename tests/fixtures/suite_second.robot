*** Settings ***
Library  pabot.PabotLib
Suite Setup    run_only_once  setup123

*** Variables ***
${FOO}=   oldvalue

*** Test Cases ***
Testing Case One of Second with Scändic Chör
  Log  pässing

Testing Case One and a half Of Second
  Fail

Testing Case Two of Second
  Fail

Testing 1
    Log   hello
    Set Global Variable  ${FOO}  newvalue

Testing 2
    Log   this should fail when running with --testlevelsplit
    Should Be Equal  ${FOO}  newvalue

*** Keywords ***
setup123
  acquire_lock  setup123
  ${VALUE}=  get_parallel_value_for_key  ONCE
  Should Be Empty  ${VALUE}
  set_parallel_value_for_key  ONCE  YEP
  release_lock  setup123