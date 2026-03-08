def first():
    x = 0
    def inner():
        nonlocal x
        x += 1
        return x
    return inner()


def second():
    y = 0
    def inner():
        nonlocal x
        x += 1
        return x
    return inner()
