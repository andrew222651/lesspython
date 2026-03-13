from sqlalchemy import case


def first(flag: bool):
    return foo(
        case(
            (flag, 1),
            else_=2,
        ),
        case(
            (flag, 3),
            else_=4,
        ),
        "x",
    )


def second(flag: bool):
    return foo(
        case(
            (flag, 1),
            else_=2,
        ),
        case(
            (flag, 3),
            else_=4,
        ),
        "y",
    )
