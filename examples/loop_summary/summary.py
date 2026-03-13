def first():
    pre = helper_one(1)
    other = helper_two(2)

    data = [1, 2, 3]
    counts = {}
    for item in data:
        name = item
        if name in counts:
            counts[name] += 1
        else:
            counts[name] = 1
    summary = [(name, count) for name, count in counts.items()]
    return summary


def second():
    pre = helper_three(10)
    other = helper_four(20)

    data = [1, 2, 3]
    counts = {}
    for item in data:
        name = item
        if name in counts:
            counts[name] += 1
        else:
            counts[name] = 1
    summary = [(name, count) for name, count in counts.items()]
    return summary
