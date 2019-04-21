*** Settings ***
Library  pabot.PabotLib

*** Test Cases ***
Laser value set
   ${setname}=  acquire_value_set   laser
   ${value}=  get_value_from_set  key
   Should Be Equal  ${value}  someval
   ${value}=  get_value_from_set  noise
   Should Be Equal  ${value}  zapp
   [Teardown]  Release Value Set

Tachyon value set
   ${setname}=  acquire_value_set   tachyon
   ${value}=  get_value_from_set  key
   Should Be Equal  ${value}  someval
   ${value}=  get_value_from_set  noise
   Should Be Equal  ${value}  zump
   [Teardown]  Release Value Set

Common value set
   ${setname}=  acquire_value_set   commontag
   ${value}=  get_value_from_set  key
   Should Be Equal  ${value}  someval
   [Teardown]  Release Value Set

None existing
   ${setname}=  acquire_value_set   nonexisting
   Log  should not get here
   [Teardown]  Release Value Set