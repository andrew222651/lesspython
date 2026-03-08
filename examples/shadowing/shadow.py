def first(x):
    y = x + 1
    def inner(x):
        return x + y
    return inner(2)


def second(a):
    b = a + 1
    def inner(a):
        return a + b
    return inner(2)
