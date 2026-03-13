import ast
import hashlib
import io
import re
import tokenize
from types import EllipsisType
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, TypeAlias, Union


@dataclass(frozen=True)
class Occurrence:
    path: Path
    lineno: int
    end_lineno: int
    line_count: int
    node_type: str


@dataclass(frozen=True)
class Span:
    start: int
    end: int


@dataclass(frozen=True)
class ErrorEntry:
    path: Path
    message: str


ConstantValue: TypeAlias = Union[
    str,
    bytes,
    int,
    float,
    complex,
    None,
    bool,
    EllipsisType,
]


@dataclass(frozen=True, order=True)
class OccurrenceSortKey:
    path_str: str
    lineno: int
    end_lineno: int
    node_type: str


@dataclass(frozen=True, order=True)
class OccurrenceSpanSortKey:
    span_len_desc: int
    path_str: str
    lineno: int


@dataclass(frozen=True, order=True)
class GroupSortKey:
    count_desc: int
    path_str: str
    lineno: int
    end_lineno: int
    hash_value: str


@dataclass(frozen=True, order=True)
class GroupOverlapSortKey:
    max_span_len_desc: int
    count_desc: int
    path_str: str
    lineno: int
    hash_value: str


@dataclass(frozen=True)
class Group:
    hash_value: str
    occurrences: List[Occurrence]


@dataclass(frozen=True)
class ScanReport:
    groups: List[Group]
    errors: List[ErrorEntry]
    python_files: int


@dataclass(frozen=True)
class NodeInfo:
    span: Span
    hash_value: str
    line_count: int
    node_type: str
    var_tokens: frozenset[str]


@dataclass
class Scope:
    mapping: Dict[str, str]
    next_id: int = 1


class AlphaRenamer(ast.NodeTransformer):
    def __init__(self, normalize_literals: bool = False) -> None:
        super().__init__()
        self._normalize_literals = normalize_literals
        self._scopes: List[Scope] = [Scope(mapping={})]
        self._rename_stack: List[bool] = [True]
        self._globals_stack: List[set[str]] = [set()]
        self._nonlocals_stack: List[set[str]] = [set()]

    def _push_scope(self) -> None:
        self._scopes.append(Scope(mapping={}))
        self._globals_stack.append(set())
        self._nonlocals_stack.append(set())

    def _pop_scope(self) -> None:
        self._scopes.pop()
        self._globals_stack.pop()
        self._nonlocals_stack.pop()

    def _push_rename(self, flag: bool) -> None:
        self._rename_stack.append(flag)

    def _pop_rename(self) -> None:
        self._rename_stack.pop()

    def _should_rename(self) -> bool:
        return self._rename_stack[-1]

    def _ensure_mapping_at(self, index: int, name: str) -> str:
        scope = self._scopes[index]
        if name not in scope.mapping:
            scope.mapping[name] = f"v{scope.next_id}"
            scope.next_id += 1
        return scope.mapping[name]

    def _canonical(self, name: str) -> str:
        scope_index = self._resolve_scope_index(name)
        return self._ensure_mapping_at(scope_index, name)

    def _resolve_scope_index(self, name: str) -> int:
        if name in self._nonlocals_stack[-1]:
            target_index = max(len(self._scopes) - 2, 0)
            self._ensure_mapping_at(target_index, name)
            return target_index
        return len(self._scopes) - 1

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self._push_scope()
        self._push_rename(True)
        try:
            return self.generic_visit(node)
        finally:
            self._pop_rename()
            self._pop_scope()

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if not self._should_rename():
            return node
        if node.id in self._globals_stack[-1]:
            return node
        return ast.copy_location(
            ast.Name(id=self._canonical(node.id), ctx=node.ctx),
            node,
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.returns = self.visit(node.returns) if node.returns else None
        self._push_scope()
        self._push_rename(True)
        try:
            node.args = self.visit(node.args)
            node.body = [self.visit(stmt) for stmt in node.body]
        finally:
            self._pop_rename()
            self._pop_scope()
        node.name = "ident"
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.returns = self.visit(node.returns) if node.returns else None
        self._push_scope()
        self._push_rename(True)
        try:
            node.args = self.visit(node.args)
            node.body = [self.visit(stmt) for stmt in node.body]
        finally:
            self._pop_rename()
            self._pop_scope()
        node.name = "ident"
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.bases = [self.visit(base) for base in node.bases]
        node.keywords = [self.visit(kw) for kw in node.keywords]
        self._push_scope()
        self._push_rename(False)
        try:
            node.body = [self.visit(stmt) for stmt in node.body]
        finally:
            self._pop_rename()
            self._pop_scope()
        node.name = "ident"
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        self._push_scope()
        self._push_rename(True)
        try:
            node.args = self.visit(node.args)
            node.body = self.visit(node.body)
        finally:
            self._pop_rename()
            self._pop_scope()
        return node

    def visit_ListComp(self, node: ast.ListComp) -> ast.AST:
        self._push_scope()
        self._push_rename(True)
        try:
            return self.generic_visit(node)
        finally:
            self._pop_rename()
            self._pop_scope()

    def visit_SetComp(self, node: ast.SetComp) -> ast.AST:
        self._push_scope()
        self._push_rename(True)
        try:
            return self.generic_visit(node)
        finally:
            self._pop_rename()
            self._pop_scope()

    def visit_DictComp(self, node: ast.DictComp) -> ast.AST:
        self._push_scope()
        self._push_rename(True)
        try:
            return self.generic_visit(node)
        finally:
            self._pop_rename()
            self._pop_scope()

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> ast.AST:
        self._push_scope()
        self._push_rename(True)
        try:
            return self.generic_visit(node)
        finally:
            self._pop_rename()
            self._pop_scope()

    def visit_arg(self, node: ast.arg) -> ast.AST:
        if self._should_rename():
            node.arg = self._canonical(node.arg)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if not self._normalize_literals:
            return node
        new_value = normalize_constant_value(node.value)
        if new_value is node.value:
            return node
        return ast.copy_location(
            ast.Constant(value=new_value, kind=getattr(node, "kind", None)),
            node,
        )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        if node.name:
            if self._should_rename():
                node.name = self._canonical(node.name)
        return self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> ast.AST:
        self._globals_stack[-1].update(node.names)
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.AST:
        self._nonlocals_stack[-1].update(node.names)
        if self._should_rename():
            node.names = [self._canonical(name) for name in node.names]
        return node

    def visit_MatchAs(self, node: ast.MatchAs) -> ast.AST:
        if node.name:
            if self._should_rename():
                node.name = self._canonical(node.name)
        return self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> ast.AST:
        if node.name:
            if self._should_rename():
                node.name = self._canonical(node.name)
        return self.generic_visit(node)

    def visit_alias(self, node: ast.alias) -> ast.AST:
        if node.asname:
            if self._should_rename():
                node.asname = self._canonical(node.asname)
        return node


def path_is_excluded(path: Path, excluded: List[Path]) -> bool:
    for base in excluded:
        if path == base or base in path.parents:
            return True
    return False


def iter_py_files(root: Path, excluded: List[Path]) -> List[Path]:
    return [
        p
        for p in root.rglob("*.py")
        if p.is_file() and not path_is_excluded(p, excluded)
    ]


def node_line_span(node: ast.AST) -> Span | None:
    lineno = getattr(node, "lineno", None)
    end_lineno = getattr(node, "end_lineno", None)
    if lineno is None or end_lineno is None:
        return None
    return Span(start=lineno, end=end_lineno)


def build_nonblank_prefix(source: str) -> List[int]:
    lines = source.splitlines()
    if not lines:
        return [0]

    code_lines = [False] * len(lines)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in {
                tokenize.ENCODING,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.COMMENT,
                tokenize.ENDMARKER,
            }:
                continue
            start_line = max(tok.start[0], 1)
            end_line = min(tok.end[0], len(lines))
            for line_no in range(start_line, end_line + 1):
                code_lines[line_no - 1] = True
    except tokenize.TokenError:
        code_lines = [bool(line.strip()) for line in lines]

    prefix = [0]
    for has_code in code_lines:
        prefix.append(prefix[-1] + (1 if has_code else 0))
    return prefix


def count_nonblank(prefix: List[int], start: int, end: int) -> int:
    if start < 1:
        start = 1
    max_index = len(prefix) - 1
    if max_index <= 0 or start > max_index:
        return 0
    if end > max_index:
        end = max_index
    if end < start:
        return 0
    return prefix[end] - prefix[start - 1]

VARNAME_RE = re.compile(r"'(?P<name>v\d+)'")
IGNORE_COMMENT = "# lesspython: ignore"


def extract_var_tokens(dump: str) -> List[str]:
    return [match.group("name") for match in VARNAME_RE.finditer(dump)]


def canonicalize_dump(dump: str, fixed_tokens: set[str] | None = None) -> str:
    mapping: Dict[str, str] = {}
    next_id = 1
    fixed = fixed_tokens or set()

    def repl(match: re.Match[str]) -> str:
        nonlocal next_id
        name = match.group("name")
        if name in fixed:
            return f"'{name}'"
        if name not in mapping:
            mapping[name] = f"v{next_id}"
            next_id += 1
        return f"'{mapping[name]}'"

    return VARNAME_RE.sub(repl, dump)


def collect_free_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Nonlocal):
            names.update(sub.names)
        elif isinstance(sub, ast.Global):
            names.update(sub.names)
    return names


def find_ignore_comments(source: str) -> List[tuple[int, int]]:
    ignores: List[tuple[int, int]] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            continue
        if tok.string.strip() == IGNORE_COMMENT:
            ignores.append((tok.start[0], tok.start[1]))
    return ignores


def build_ignored_spans(
    tree: ast.AST, ignore_comments: List[tuple[int, int]], source_lines: List[str]
) -> List[Span]:
    ignored: List[Span] = []
    if not ignore_comments:
        return ignored
    for node in ast.walk(tree):
        for field_name in ("body", "orelse", "finalbody"):
            value = getattr(node, field_name, None)
            if not isinstance(value, list):
                continue
            statements = [stmt for stmt in value if isinstance(stmt, ast.stmt)]
            if not statements:
                continue
            col_offsets = [
                getattr(stmt, "col_offset", None)
                for stmt in statements
                if getattr(stmt, "col_offset", None) is not None
            ]
            if not col_offsets:
                continue
            indent = min(col_offsets)
            first_line = min(
                stmt.lineno for stmt in statements if hasattr(stmt, "lineno")
            )
            end_line = max(
                stmt.end_lineno for stmt in statements if hasattr(stmt, "end_lineno")
            )
            start_line = first_line
            while start_line > 1:
                prev_line = source_lines[start_line - 2]
                if not prev_line.strip():
                    start_line -= 1
                    continue
                if prev_line.startswith(" " * indent) and prev_line.lstrip().startswith("#"):
                    start_line -= 1
                    continue
                break
            for line_no, col in ignore_comments:
                if col != indent:
                    continue
                if start_line <= line_no <= end_line:
                    parent_span = node_line_span(node)
                    if parent_span is None:
                        parent_span = Span(start=start_line, end=end_line)
                    ignored.append(parent_span)
                    break
    return ignored


def span_within_ignored(span: Span, ignored: List[Span]) -> bool:
    for ignored_span in ignored:
        if span.start >= ignored_span.start and span.end <= ignored_span.end:
            return True
    return False


def add_occurrence(
    by_hash: Dict[str, List[Occurrence]], hash_value: str, occ: Occurrence
) -> None:
    by_hash.setdefault(hash_value, []).append(occ)


def build_node_cache(
    tree: ast.AST, nonblank_prefix: List[int]
) -> Dict[int, NodeInfo]:
    cache: Dict[int, NodeInfo] = {}
    for node in ast.walk(tree):
        span = node_line_span(node)
        if not span:
            continue
        dump = ast.dump(node, include_attributes=False)
        free_names = collect_free_names(node)
        free_tokens = [
            name for name in free_names if name.startswith("v") and name[1:].isdigit()
        ]
        canonical_dump = canonicalize_dump(dump, fixed_tokens=set(free_tokens))
        h = hashlib.sha256(canonical_dump.encode("utf-8")).hexdigest()
        line_count = count_nonblank(nonblank_prefix, span.start, span.end)
        var_tokens = frozenset(extract_var_tokens(dump))
        cache[id(node)] = NodeInfo(
            span=span,
            hash_value=h,
            line_count=line_count,
            node_type=type(node).__name__,
            var_tokens=var_tokens,
        )
    return cache


def collect_hashes(
    tree: ast.AST,
    min_lines: int,
    path: Path,
    nonblank_prefix: List[int],
    ignored_spans: List[Span],
) -> Dict[str, List[Occurrence]]:
    by_hash: Dict[str, List[Occurrence]] = {}
    cache = build_node_cache(tree, nonblank_prefix)
    for info in cache.values():
        if info.line_count < min_lines:
            continue
        if info.node_type in {"Import", "ImportFrom"}:
            continue
        if span_within_ignored(info.span, ignored_spans):
            continue
        add_occurrence(
            by_hash,
            info.hash_value,
            Occurrence(
                path=path,
                lineno=info.span.start,
                end_lineno=info.span.end,
                line_count=info.line_count,
                node_type=info.node_type,
            ),
        )

    for node in ast.walk(tree):
        for field_name in node._fields:
            value = getattr(node, field_name, None)
            if not isinstance(value, list):
                continue
            config = sequence_config(node, field_name)
            if config is None:
                continue
            node_types, excluded_node_types, label = config
            sequence_nodes = [
                item for item in value if isinstance(item, node_types)
            ]
            if not sequence_nodes:
                continue
            nodes_with_span = [
                item
                for item in sequence_nodes
                if hasattr(item, "lineno") and hasattr(item, "end_lineno")
            ]
            if not nodes_with_span:
                continue
            list_span = Span(
                start=min(item.lineno for item in nodes_with_span),
                end=max(item.end_lineno for item in nodes_with_span),
            )
            if span_within_ignored(list_span, ignored_spans):
                continue
            add_sequences_from_list(
                value,
                min_lines,
                path,
                by_hash,
                cache,
                nonblank_prefix,
                node_types=node_types,
                excluded_node_types=excluded_node_types,
                label=label,
            )
    return by_hash


def normalize_constant_value(value: ConstantValue) -> ConstantValue:
    if value is None or value is Ellipsis:
        return value
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, float):
        return 0.0
    if isinstance(value, complex):
        return 0j
    if isinstance(value, str):
        return "const"
    if isinstance(value, bytes):
        return b"const"
    return value


def spans_overlap(a: Occurrence, b_span: Span) -> bool:
    return not (a.end_lineno < b_span.start or b_span.end < a.lineno)


def add_sequences_from_list(
    values: List[object],
    min_lines: int,
    path: Path,
    by_hash: Dict[str, List[Occurrence]],
    cache: Dict[int, NodeInfo],
    nonblank_prefix: List[int],
    node_types: tuple[type[ast.AST], ...],
    excluded_node_types: set[str],
    label: str,
) -> None:
    nodes: List[NodeInfo] = []
    for value in values:
        if isinstance(value, node_types):
            info = cache.get(id(value))
            if info is not None and info.node_type not in excluded_node_types:
                nodes.append(info)

    count = len(nodes)
    if count < 2:
        return

    for start_index in range(count - 1):
        start_span = nodes[start_index].span
        max_end_span = nodes[count - 1].span
        if (
            count_nonblank(nonblank_prefix, start_span.start, max_end_span.end)
            < min_lines
        ):
            break

        hasher = hashlib.sha256()
        token_masks: Dict[str, int] = {}
        for end_index in range(start_index, count):
            hasher.update(nodes[end_index].hash_value.encode("utf-8"))
            hasher.update(b"\n")
            bit = 1 << (end_index - start_index)
            for token in nodes[end_index].var_tokens:
                token_masks[token] = token_masks.get(token, 0) | bit
            if end_index == start_index:
                continue
            end_span = nodes[end_index].span
            lineno = start_span.start
            line_count = count_nonblank(nonblank_prefix, lineno, end_span.end)
            if line_count < min_lines:
                continue
            linkage_masks = [
                mask for mask in token_masks.values() if mask.bit_count() >= 2
            ]
            linkage_hasher = hashlib.sha256()
            for mask in sorted(linkage_masks):
                linkage_hasher.update(str(mask).encode("utf-8"))
                linkage_hasher.update(b"\n")
            sequence_hasher = hashlib.sha256()
            sequence_hasher.update(hasher.digest())
            sequence_hasher.update(b"\n")
            sequence_hasher.update(linkage_hasher.digest())
            h = sequence_hasher.hexdigest()
            add_occurrence(
                by_hash,
                h,
                Occurrence(
                    path=path,
                    lineno=lineno,
                    end_lineno=end_span.end,
                    line_count=line_count,
                    node_type=f"{label}[{end_index - start_index + 1}]",
                ),
            )


STMT_SEQUENCE_FIELDS = {"body", "orelse", "finalbody"}
STMT_SEQUENCE_PARENT_TYPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
    ast.Match,
    ast.match_case,
)

EXPR_SEQUENCE_FIELDS = {"args", "elts"}
EXPR_SEQUENCE_PARENT_TYPES = (
    ast.Call,
    ast.Tuple,
    ast.List,
    ast.Set,
)


def sequence_config(
    node: ast.AST, field_name: str
) -> tuple[tuple[type[ast.AST], ...], set[str], str] | None:
    if field_name in STMT_SEQUENCE_FIELDS and isinstance(
        node, STMT_SEQUENCE_PARENT_TYPES
    ):
        return (ast.stmt,), {"Import", "ImportFrom"}, "StmtSequence"
    if field_name in EXPR_SEQUENCE_FIELDS and isinstance(
        node, EXPR_SEQUENCE_PARENT_TYPES
    ):
        return (ast.expr,), set(), "ExprSequence"
    return None


def select_non_overlapping_occurrences(
    occurrences: List[Occurrence],
) -> List[Occurrence]:
    sorted_occs = sorted(
        occurrences,
        key=lambda occ: OccurrenceSpanSortKey(
            span_len_desc=-occ.line_count,
            path_str=str(occ.path),
            lineno=occ.lineno,
        ),
    )
    selected: List[Occurrence] = []
    selected_by_file: Dict[Path, List[Span]] = {}

    for occ in sorted_occs:
        spans = selected_by_file.setdefault(occ.path, [])
        if any(spans_overlap(occ, span) for span in spans):
            continue
        spans.append(Span(start=occ.lineno, end=occ.end_lineno))
        selected.append(occ)

    return selected


def reduce_group_overlaps(
    duplicates: Dict[str, List[Occurrence]],
) -> List[Group]:
    groups: List[Group] = []
    for h in duplicates:
        occs = select_non_overlapping_occurrences(duplicates[h])
        if len(occs) > 1:
            groups.append(Group(hash_value=h, occurrences=occs))
    return groups


def filter_groups_global(groups: List[Group]) -> List[Group]:
    ordered = sorted(
        groups,
        key=lambda group: GroupOverlapSortKey(
            max_span_len_desc=-max(occ.line_count for occ in group.occurrences),
            count_desc=-len(group.occurrences),
            path_str=str(group.occurrences[0].path),
            lineno=group.occurrences[0].lineno,
            hash_value=group.hash_value,
        ),
    )
    selected_by_file: Dict[Path, List[Span]] = {}
    filtered_groups: List[Group] = []
    for group in ordered:
        occs = sorted(
            group.occurrences,
            key=lambda o: OccurrenceSortKey(
                path_str=str(o.path),
                lineno=o.lineno,
                end_lineno=o.end_lineno,
                node_type=o.node_type,
            ),
        )
        kept: List[Occurrence] = []
        for occ in occs:
            spans = selected_by_file.setdefault(occ.path, [])
            if any(spans_overlap(occ, span) for span in spans):
                continue
            spans.append(Span(start=occ.lineno, end=occ.end_lineno))
            kept.append(occ)
        if len(kept) > 1:
            filtered_groups.append(
                Group(hash_value=group.hash_value, occurrences=kept)
            )

    return filtered_groups


def resolve_excludes(root: Path, excludes: List[Path]) -> List[Path]:
    resolved: List[Path] = []
    for item in excludes:
        candidate = item
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved.append(candidate.resolve())
    return resolved


def scan_folder(
    folder: Path,
    min_lines: int,
    normalize_literals: bool,
    exclude_paths: List[Path] | None = None,
) -> ScanReport:
    root = folder.resolve()
    excludes = resolve_excludes(root, exclude_paths or [])
    files = iter_py_files(root, excludes)
    if not files:
        return ScanReport(groups=[], errors=[], python_files=0)

    normalizer = AlphaRenamer(normalize_literals=normalize_literals)
    all_hashes: Dict[str, List[Occurrence]] = {}
    errors: List[ErrorEntry] = []

    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            nonblank_prefix = build_nonblank_prefix(source)
            tree = ast.parse(source, filename=str(path))
            tree = normalizer.visit(tree)
            ast.fix_missing_locations(tree)
            ignore_comments = find_ignore_comments(source)
            ignored_spans = build_ignored_spans(
                tree, ignore_comments, source.splitlines()
            )
            per_file = collect_hashes(
                tree,
                min_lines=min_lines,
                path=path,
                nonblank_prefix=nonblank_prefix,
                ignored_spans=ignored_spans,
            )
            for h in per_file:
                for occ in per_file[h]:
                    all_hashes.setdefault(h, []).append(occ)
        except SyntaxError as e:
            errors.append(ErrorEntry(path=path, message=f"SyntaxError: {e}"))
        except UnicodeDecodeError as e:
            errors.append(
                ErrorEntry(path=path, message=f"UnicodeDecodeError: {e}")
            )

    duplicates: Dict[str, List[Occurrence]] = {}
    for h in all_hashes:
        if len(all_hashes[h]) > 1:
            duplicates[h] = all_hashes[h]

    if not duplicates:
        return ScanReport(groups=[], errors=errors, python_files=len(files))

    groups = reduce_group_overlaps(duplicates)
    groups = filter_groups_global(groups)
    return ScanReport(groups=groups, errors=errors, python_files=len(files))
