def one(flag):
    try:
        if flag:
            x = 1
            x += 2
            return x
    except Exception:
        return 0


def two(ok):
    try:
        if ok:
            y = 1
            y += 2
            return y
    except Exception:
        return 0
