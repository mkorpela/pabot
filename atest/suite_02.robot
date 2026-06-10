*** Settings ***
Resource    ConcurrencyTracking.resource
Test Setup    Start Concurrent Test    ${TEST NAME}
Test Teardown    Stop Concurrent Test    ${TEST NAME}
Documentation    Normal parallel suite 02

*** Test Cases ***
Normal Test 02 A
    Log    Running normal test 02-A in parallel
    Sleep    0.05s

Normal Test 02 B
    Log    Running normal test 02-B in parallel
    Sleep    0.05s
