*** Settings ***
Library    Dialogs
Library    pabot.pabotlib

*** Keywords ***
Step 1
    [Arguments]    ${arg1}
    Log    Running ${arg1}

Login
    Acquire Value Set    credentials_admin
    ${username}=    Get Value From Set    username
    ${password}=    Get Value From Set    password
    Log    Logging in with ${username} and ${password}
    VAR    ${token}    Some token for further usage
    Set Parallel Value For Key    MY_TOKEN    ${token}

Logout
    Release Value Set

Use Bottleneck
    Acquire Lock    Bottleneck
    Dialogs.Pause Execution    I am in the concurrent section - this window should appear only once
    Release Lock    Bottleneck

Use Token Somewhere
    ${token}=    Get Parallel Value For Key    MY_TOKEN
    Log    Using token ${token}