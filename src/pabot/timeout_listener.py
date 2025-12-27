ROBOT_LISTENER_API_VERSION = 3

def end_test(data, result):
    result.status = 'FAIL'
    result.message = "Pabot's --processtimeout option has been reached."
