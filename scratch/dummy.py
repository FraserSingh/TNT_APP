import pandas as pd

# packages should be sorted
s = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})


def fak_test(s):
    print(f"Hello {s} world")  # should error for empty f string
