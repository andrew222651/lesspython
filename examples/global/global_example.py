VALUE = 0


def first():
    global VALUE
    VALUE += 1
    return VALUE


TOTAL = 0


def second():
    global TOTAL
    TOTAL += 1
    return TOTAL
