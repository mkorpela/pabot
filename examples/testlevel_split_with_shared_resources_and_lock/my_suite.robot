*** Settings ***
Resource    my_keywords.resource

Test Setup    Login
Test Teardown    Logout

*** Test Cases ***
My Test 1
    Step 1    hello from test 1
    Use Bottleneck
    Use Token Somewhere

My Test 2
    Step 1    hello from test 2
    Use Bottleneck
    Use Token Somewhere

My Test 3
    Step 1    hello from test 3
    Use Bottleneck
    Use Token Somewhere
