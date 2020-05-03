*** Settings ***
Library  OperatingSystem

*** Variables ***
${Screenshot in root}  fake_screenshot_root_${SUITE NAME}.png
${Screenshot in subfolder 1}  screenshots${/}fake_screenshot_subfolder_1_${SUITE NAME}.png
${Screenshot in subfolder 2}  screenshots${/}fake_screenshot_subfolder_2_${SUITE NAME}.png
${Artifact in subfolder 1}  other_artifacts${/}some_artifact_${SUITE NAME}.foo
${Artifact in subfolder 2}  other_artifacts${/}another_artifact_${SUITE NAME}.bar

*** Keywords ***
Create artifact file
  [Arguments]  ${rel_path}
  ${abs_path}=  Set variable  ${OUTPUT DIR}${/}${rel_path}
  ${exists}=  Run Keyword And Return Status  File Should Exist  ${abs_path}
  Return from keyword if  ${exists}
  Create file  ${abs_path}  test

Create all artifact files
  Create artifact file  ${Screenshot in root}
  Create artifact file  ${Screenshot in subfolder 1}
  Create artifact file  ${Screenshot in subfolder 2}
  Create artifact file  ${Artifact in subfolder 1}
  Create artifact file  ${Artifact in subfolder 2}

Log screenshot
  [Arguments]  ${path}
  Log  html=${True}  message=Screenshot example <a href="${path}"><img src="${path}"></a>

Log file link
  [Arguments]  ${path}
  Log  html=${True}  message=File link example: <a href="${path}">${path}</a>