def first(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        return str(e)


def second(path):
    try:
        with open(path) as handle:
            return handle.read()
    except Exception as err:
        return str(err)
