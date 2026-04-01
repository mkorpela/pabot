*** Settings ***
Test Template    Log Loop

*** Test Cases ***
Stream 01    _
Stream 02    _
Stream 03    _
Stream 04    _
Stream 05    _
Stream 06    _
Stream 07    _
Stream 08    _
Stream 09    _
Stream 10    _
Stream 11    _
Stream 12    _
Stream 13    _
Stream 14    _
Stream 15    _
Stream 16    _
Stream 17    _
Stream 18    _
Stream 19    _
Stream 20    _
Stream 21    _
Stream 22    _
Stream 23    _
Stream 24    _
Stream 25    _
Stream 26    _
Stream 27    _
Stream 28    _
Stream 29    _
Stream 30    _

*** Keywords ***
Log Loop
    [Arguments]    ${dummy}
    FOR    ${i}    IN RANGE    5
        Log To Console    step ${i}
        Sleep    0.1s
    END