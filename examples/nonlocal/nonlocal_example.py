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
        nonlocal y
        y += 1
        return y
    return inner()
