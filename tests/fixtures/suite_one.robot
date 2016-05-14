*** Settings ***
Library  pabot.PabotLib
Suite Setup    run_only_once  setup123

*** Test Cases ***
1.1 Test Case One
  Log  testing
  Sleep  16 seconds
  Log  this is long running

1.2 Test Case Two
  ${VALUE}=  get_parallel_value_for_key  Key
  Should Be Equal  ${VALUE}  Value
  acquire_lock  MyLock
  release_lock  MyLock

*** Keywords ***
setup123
  acquire_lock  setup123
  ${VALUE}=  get_parallel_value_for_key  ONCE
  Should Be Empty  ${VALUE}
  set_parallel_value_for_key  ONCE  YEP
  release_lock  setup123