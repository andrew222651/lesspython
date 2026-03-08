def first(obj):
    obj.foo = 1
    obj.bar = 2
    return obj.foo + obj.bar


def second(obj):
    obj.baz = 1
    obj.qux = 2
    return obj.baz + obj.qux
