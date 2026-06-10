*** Settings ***
Documentation    Shared keywords for tracking concurrent test execution.
...
...              Normal tests call Start Concurrent Test / Stop Concurrent Test
...              via Test Setup / Test Teardown in their suite settings.
...
...              Exclusive tests use Start Exclusive Test instead, which
...              additionally asserts no other test is running in parallel.
Library          ConcurrencyTracker.py    WITH NAME    Tracker

*** Keywords ***
Start Concurrent Test
    [Documentation]    Register this test as currently running.
    [Arguments]    ${name}
    Tracker.Mark Running    ${name}

Start Exclusive Test
    [Documentation]    Register this exclusive test as running, then assert
    ...    it is the only active test. A 30 ms grace-period sleep gives any
    ...    truly concurrent test time to register itself first.
    [Arguments]    ${name}
    Tracker.Mark Running    ${name}
    Sleep    0.03s
    Tracker.Assert Running Alone    ${name}

Stop Concurrent Test
    [Documentation]    Unregister this test (call from Test Teardown).
    [Arguments]    ${name}
    Tracker.Mark Done    ${name}
