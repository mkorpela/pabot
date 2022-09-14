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

Add value to set
    ${my_value_set1_name}=  Set Variable  MyValueSet1
    &{my_value_set1_dict}=  Create Dictionary  key=someVal1  tags=valueset1,common  commonkey=common
    ${my_value_set2_name}=  Set Variable  MyValueSet2
    &{my_value_set2_dict}=  Create Dictionary  key=someVal2  tags=valueset2,common  commonkey=common
    Add Value To Set  ${my_value_set1_name}  ${my_value_set1_dict}
    ${setname}=  Acquire Value Set  common
    ${value}=  Get Value From Set  commonkey
    Should Be Equal  ${value}  common
    Release Value Set
    ${setname}=  Acquire Value Set  valueset1
    ${value}=  Get Value From Set  key
    Should Be Equal  ${value}  someVal1
    Release Value Set
    ${setname}=  Acquire Value Set  valueset2
    ${value}=  Get Value From Set  key
    Should Be Equal  ${value}  someVal2
    [Teardown]  Release Value Set