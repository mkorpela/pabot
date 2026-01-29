ROBOT_LISTENER_API_VERSION = 3

def end_test(data, result):
    result.status = 'FAIL'
    result.message = "Pabot's --processtimeout option has been reached. Unfortunately, this test could not be completed in time and there is no original data available."
