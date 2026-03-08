def first(value):
    match value:
        case {"x": y}:
            return y
        case _:
            return None


def second(value):
    match value:
        case {"x": z}:
            return z
        case _:
            return None
