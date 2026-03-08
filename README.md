# lesspython

Find duplicated Python code fragments by hashing normalized AST subtrees.

## Usage

```bash
lesspython /path/to/project --min-lines 5
```

Normalize literals to ignore constant differences:

```bash
lesspython /path/to/project --min-lines 5 --normalize-literals
```

Exclude paths (repeatable):

```bash
lesspython /path/to/project -e .venv -e build -e tests
```

## Ignore blocks

Add `# lesspython: ignore` on its own line at the top level inside a block to exclude that block
from duplication detection. For example, to skip a function:

```python
def noisy():
    # lesspython: ignore
    ...
```

For nested blocks (e.g., an `if` inside a function), only the statements within that `if`
block are ignored. The enclosing function can still be reported as duplicate if other
parts match.

## Output

The CLI prints YAML with these top-level keys:

- `python_files`: number of Python files scanned
- `errors`: parse/encoding errors
- `groups`: duplicate fragment groups with occurrences and spans

## Development

## Install

```bash
pip install -e .[dev]
```

Run tests:

```bash
python -m unittest discover -s tests
```
