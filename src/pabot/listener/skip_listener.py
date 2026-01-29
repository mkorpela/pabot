ROBOT_LISTENER_API_VERSION = 3

def end_test(data, result):
    # data: TestCase object
    # result: TestCaseResult object
    result.status = 'SKIP'
    result.message = "Pabot skip logic: this test was skipped due to dependencies and failure policy."
