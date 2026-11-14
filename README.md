# Fly-in Map Generator

Dependency-free Python library that creates valid Fly-in map text.

```python
from flyin_map_generator import RandomizationPolicy, generate_map_text

text = generate_map_text(10, 25, 35, RandomizationPolicy(seed=42))
```

The returned string is UTF-8-ready Fly-in input and can be saved directly as a `.txt` file.
