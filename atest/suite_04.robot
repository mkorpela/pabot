*** Settings ***
Resource    ConcurrencyTracking.resource
Documentation    Mixed suite: one parallel test and one exclusive test

*** Test Cases ***
Normal Test 04
    [Setup]    Start Concurrent Test    ${TEST NAME}
    [Teardown]    Stop Concurrent Test    ${TEST NAME}
    Log    This test runs in parallel with other normal tests
    Sleep    0.05s

Exclusive Test 04
    [Tags]    pabot:exclusive
    [Setup]    Start Exclusive Test    ${TEST NAME}
    [Teardown]    Stop Concurrent Test    ${TEST NAME}
    Log    This test runs exclusively — no other test runs in parallel
    Sleep    0.3s
