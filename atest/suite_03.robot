*** Settings ***
Resource    ConcurrencyTracking.resource
Test Setup    Start Concurrent Test    ${TEST NAME}
Test Teardown    Stop Concurrent Test    ${TEST NAME}
Documentation    Normal parallel suite 03

*** Test Cases ***
Normal Test 03 A
    Log    Running normal test 03-A in parallel
    Sleep    0.05s

Normal Test 03 B
    Log    Running normal test 03-B in parallel
    Sleep    0.05s
