"""Fake mínimo do client do Supabase pros testes de service.

Cobre só o subconjunto de operações que o backend usa. Não tenta emular
PostgREST inteiro — o que depende de semântica real do Postgres (ex: o
`or_` da paginação por cursor) é verificado pelos testes que checam a
*query montada*, não o resultado filtrado.
"""

from dataclasses import dataclass, field


@dataclass
class FakeResult:
    data: object


@dataclass
class RecordedQuery:
    table: str
    op: str
    filters: dict = field(default_factory=dict)
    or_clauses: list = field(default_factory=list)
    order_by: list = field(default_factory=list)
    limit_value: int | None = None
    payload: object = None


class FakeQuery:
    def __init__(self, db, table_name):
        self._db = db
        self._q = RecordedQuery(table=table_name, op="select")

    def insert(self, payload):
        self._q.op = "insert"
        self._q.payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self._q.op = "upsert"
        self._q.payload = payload
        return self

    def update(self, payload):
        self._q.op = "update"
        self._q.payload = payload
        return self

    def delete(self):
        self._q.op = "delete"
        return self

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._q.filters[key] = value
        return self

    def in_(self, key, values):
        self._q.filters[f"{key}__in"] = list(values)
        return self

    def gte(self, key, value):
        self._q.filters[f"{key}__gte"] = value
        return self

    def lt(self, key, value):
        self._q.filters[f"{key}__lt"] = value
        return self

    def lte(self, key, value):
        self._q.filters[f"{key}__lte"] = value
        return self

    def is_(self, key, value):
        assert value == "null", "fake só suporta is_(key, 'null')"
        self._q.filters[f"{key}__isnull"] = True
        return self

    def or_(self, clause):
        self._q.or_clauses.append(clause)
        return self

    def order(self, column, desc=False):
        self._q.order_by.append((column, desc))
        return self

    def limit(self, value):
        self._q.limit_value = value
        return self

    def maybe_single(self):
        self._q.op = f"{self._q.op}_single"
        return self

    def execute(self):
        return self._db.execute(self._q)


class FakeDb:
    """`tables` mapeia nome -> lista de linhas (dicts)."""

    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self.tables = {name: list(rows) for name, rows in (tables or {}).items()}
        self.queries: list[RecordedQuery] = []
        self._next_id = 1000

    def table(self, name):
        return FakeQuery(self, name)

    def rows(self, name) -> list[dict]:
        return self.tables.setdefault(name, [])

    def execute(self, q: RecordedQuery):
        self.queries.append(q)
        rows = self.rows(q.table)

        if q.op in ("insert", "upsert"):
            payload = q.payload if isinstance(q.payload, list) else [q.payload]
            created = []
            for item in payload:
                row = {**item}
                row.setdefault("id", self._next_id)
                self._next_id += 1
                rows.append(row)
                created.append(row)
            return FakeResult(data=created)

        matched = [row for row in rows if _matches(row, q.filters)]

        if q.op == "update":
            for row in matched:
                row.update(q.payload)
            return FakeResult(data=matched)

        if q.op == "delete":
            for row in matched:
                rows.remove(row)
            return FakeResult(data=matched)

        for column, desc in reversed(q.order_by):
            matched.sort(key=lambda row: row.get(column), reverse=desc)

        if q.op == "select_single":
            return FakeResult(data=matched[0]) if matched else None

        if q.limit_value is not None:
            matched = matched[: q.limit_value]

        return FakeResult(data=matched)


def _matches(row: dict, filters: dict) -> bool:
    for key, expected in filters.items():
        if key.endswith("__in"):
            if row.get(key[:-4]) not in expected:
                return False
        elif key.endswith("__gte"):
            if str(row.get(key[:-5])) < str(expected):
                return False
        elif key.endswith("__lte"):
            if str(row.get(key[:-5])) > str(expected):
                return False
        elif key.endswith("__lt"):
            if str(row.get(key[:-4])) >= str(expected):
                return False
        elif key.endswith("__isnull"):
            if row.get(key[:-8]) is not None:
                return False
        elif row.get(key) != expected:
            return False
    return True
