ROBOT_LISTENER_API_VERSION = 3

def end_test(data, result):
    result.status = 'FAIL'
    result.message = "User interrupted Pabot execution (Ctrl+C) when this test/suite was running. Unfortunately, there is no original data available."
