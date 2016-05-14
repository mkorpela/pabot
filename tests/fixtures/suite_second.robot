*** Settings ***
Library  pabot.PabotLib

*** Test Cases ***
Testing Case One of Second
  set_parallel_value_for_key  Key  Value

Testing Case One and a half Of Second
  Fail

Testing Case Two of Second
  Fail