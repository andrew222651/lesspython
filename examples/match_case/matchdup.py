def first(value):
    match value:
        case 1:
            x = 10
            x += 1
            return x
        case _:
            return 0


def second(value):
    match value:
        case 1:
            y = 10
            y += 1
            return y
        case _:
            return 0
