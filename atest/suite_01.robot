*** Settings ***
Resource    ConcurrencyTracking.resource
Test Setup    Start Concurrent Test    ${TEST NAME}
Test Teardown    Stop Concurrent Test    ${TEST NAME}
Documentation    Normal parallel suite 01

*** Test Cases ***
Normal Test 01 A
    Log    Running normal test 01-A in parallel
    Sleep    0.05s

Normal Test 01 B
    Log    Running normal test 01-B in parallel
    Sleep    0.05s
