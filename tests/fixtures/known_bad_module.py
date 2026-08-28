import os


def process_data(data, config=None, flags=None, limit=10, offset=0, verbose=False, items=[]):
    for i in range(len(data)):
        if data[i] == True:
            items.append(data[i])

    try:
        risky_operation()
    except:
        pass

    if type(data) == list:
        pass

    if verbose == True:
        pass

    return items, 42


def compute_total_a(items):
    total = 0
    for item in items:
        total = total + item
    return total


def compute_total_b(values):
    result = 0
    for value in values:
        result = result + value
    return result


def _never_called_helper():
    return 1
