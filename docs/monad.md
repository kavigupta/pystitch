
# Basic Monad?

```python
def f(x, y, z):
    a = y * z
    print(a)
    return x + a
```

```python
(lambda (x y z)
    (>>=
        (pure (* y z))
        (lambda (a)
            (>>=
                (print a)
                (lambda (_)
                    (pure
                        (+ a x)))))))
```

But how do we handle nontrivial control flow?

```python
def f(x):
    if x > 0:
        x = -x
    return x
```

Seems problematic that we can't represent (x = -x) even. Maybe factor out `if` to return new values for relevant variables?