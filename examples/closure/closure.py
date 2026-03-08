def first(values):
    total = 0
    def inner():
        return total + 1
    return inner()


def second(items):
    count = 0
    def inner():
        return count + 1
    return inner()
