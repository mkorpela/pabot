*** Settings ***
Library  pabot.PabotLib
Suite Setup    run_only_once  setup123

*** Test Cases ***
1.1 Test Case One
  Log  testing
  Sleep  16 seconds
  Log  this is long running

1.2 Test Case Two
  acquire_lock  MyLock
  ${VALUE}=  get_parallel_value_for_key  Key
  set_parallel_value_for_key  Key  Value
  release_lock  MyLock
  Should Be Equal  ${VALUE}  Value

1.3 Test Value Set
  acquire_value_set
  ${value}=  get_value_from_set  mystuff
  Should Be Equal  ${value}  FromSet
  ${value}=  get_value_from_set  MYSTUFF
  Should Be Equal  ${value}  FromSet
  release_value_set

1.4 Testing arg file
  Should Be Equal  ${PASSINGARG}  Yep

*** Keywords ***
setup123
  acquire_lock  setup123
  ${VALUE}=  get_parallel_value_for_key  ONCE
  Should Be Empty  ${VALUE}
  set_parallel_value_for_key  ONCE  YEP
  release_lock  setup123