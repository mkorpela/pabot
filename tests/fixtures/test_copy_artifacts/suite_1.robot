*** Settings ***
Resource  keywords.robot
Suite Setup  Create all artifact files

*** Test Cases ***
Links to screenshot directly in output_dir
  Log screenshot  ${Screenshot in root}

Links to screenshots in subfolder
  Log screenshot  ${Screenshot in subfolder 1}
  Log screenshot  ${Screenshot in subfolder 2}

Links to other file in subfolder
  Log file link  ${Artifact in subfolder 1}
  Log file link  ${Artifact in subfolder 2}