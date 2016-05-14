*** Settings ***
Library  PabotLib

*** Test Cases ***
1.1 Test Case One
  Log  testing
  Sleep  31 seconds
  Log  this is long running

1.2 Test Case Two
  ${VALUE}=  get_parallel_value_for_key  Key
  Should Be Equal  ${VALUE}  Value