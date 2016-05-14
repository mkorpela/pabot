*** Settings ***
Library  pabot.PabotLib
Suite Setup    run_only_once  setup123

*** Test Cases ***
Testing Case One of Second
  acquire_lock  MyLock
  set_parallel_value_for_key  Key  Value
  release_lock  MyLock

Testing Case One and a half Of Second
  Fail

Testing Case Two of Second
  Fail

*** Keywords ***
setup123
  acquire_lock  setup123
  ${VALUE}=  get_parallel_value_for_key  ONCE
  Should Be Empty  ${VALUE}
  set_parallel_value_for_key  ONCE  YEP
  release_lock  setup123