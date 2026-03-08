def first(path):
    with open(path) as f:
        data = f.read()
        data = data.strip()
        return data


def second(path):
    with open(path) as handle:
        text = handle.read()
        text = text.strip()
        return text
