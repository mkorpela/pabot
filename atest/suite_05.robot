*** Settings ***
Resource    ConcurrencyTracking.resource
Test Setup    Start Exclusive Test    ${TEST NAME}
Test Teardown    Stop Concurrent Test    ${TEST NAME}
Documentation    Exclusive suite: both tests must run completely alone

*** Test Cases ***
Exclusive Test 05 A
    [Tags]    pabot:exclusive
    Log    Exclusive test — no parallel execution allowed
    Sleep    0.3s

Exclusive Test 05 B
    [Tags]    pabot:exclusive
    Log    Exclusive test — no parallel execution allowed
    Sleep    0.3s
