*** Test Cases ***
Funny
  Recursive  1

*** Keywords ***
Recursive  
   [Arguments]  ${ars}
   Run keyword if   '${ars}' == '1'   Recursion  2
