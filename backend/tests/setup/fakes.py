import itertools
from uuid import uuid4

from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment

_timestamp_counter = itertools.count(1)


def _resolve(value):
    if value is SERVER_TIMESTAMP:
        return next(_timestamp_counter)
    return value


class FakeDocSnapshot:
    """Stand-in for a Firestore DocumentSnapshot."""

    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeDocRef:
    """Stand-in for a Firestore DocumentReference, backed by a shared node
    dict of the shape {"data": {...}, "subcollections": {name: {doc_id: node}}}.
    """

    def __init__(self, collection, doc_id):
        self._collection = collection
        self._id = doc_id

    @property
    def id(self):
        return self._id

    def _node(self, create=False):
        node = self._collection._docs.get(self._id)
        if node is None and create:
            node = {"data": {}, "subcollections": {}}
            self._collection._docs[self._id] = node
        return node

    def get(self):
        node = self._node()
        return FakeDocSnapshot(self._id, dict(node["data"]) if node else None)

    def set(self, data, merge=False):
        node = self._node(create=True)
        if not merge:
            node["data"] = {}
        for key, value in data.items():
            if isinstance(value, Increment):
                node["data"][key] = node["data"].get(key, 0) + value.value
            else:
                node["data"][key] = _resolve(value)

    def update(self, data):
        node = self._node()
        if node is None:
            raise KeyError(f"No document to update at id {self._id!r}")
        for key, value in data.items():
            if isinstance(value, Increment):
                node["data"][key] = node["data"].get(key, 0) + value.value
            else:
                node["data"][key] = _resolve(value)

    def delete(self):
        self._collection._docs.pop(self._id, None)

    def collection(self, name):
        node = self._node(create=True)
        sub_store = node["subcollections"].setdefault(name, {})
        return FakeCollection(sub_store)


class FakeCollection:
    """Stand-in for a Firestore CollectionReference/Query, backed by a shared
    dict of {doc_id: {"data": {...}, "subcollections": {...}}}.
    """

    def __init__(self, docs_store):
        self._docs = docs_store
        self._filters: list[tuple[str, str, object]] = []
        self._order: tuple[str, str] | None = None
        self._limit: int | None = None

    def document(self, doc_id=None):
        if doc_id is None:
            doc_id = uuid4().hex
        return FakeDocRef(self, doc_id)

    def where(self, field, op, value):
        clone = self._clone()
        clone._filters.append((field, op, value))
        return clone

    def order_by(self, field, direction="ASCENDING"):
        clone = self._clone()
        clone._order = (field, direction)
        return clone

    def limit(self, n):
        clone = self._clone()
        clone._limit = n
        return clone

    def stream(self):
        return [FakeDocSnapshot(doc_id, dict(data)) for doc_id, data in self._matching()]

    def _clone(self):
        clone = FakeCollection(self._docs)
        clone._filters = list(self._filters)
        clone._order = self._order
        clone._limit = self._limit
        return clone

    def _matching(self):
        items = [(doc_id, node["data"]) for doc_id, node in self._docs.items()]
        for field, op, value in self._filters:
            if op != "==":
                raise NotImplementedError(f"FakeCollection.where does not support {op!r}")
            items = [(doc_id, data) for doc_id, data in items if data.get(field) == value]
        if self._order:
            field, direction = self._order
            items.sort(key=lambda item: item[1].get(field) or 0, reverse=direction == "DESCENDING")
        if self._limit is not None:
            items = items[: self._limit]
        return items


class FakeFirestore:
    """Stand-in for a Firestore Client, in-memory, supports any number of
    top-level collections and arbitrarily nested subcollections.

    `seed={"users": {uid: {...}}}` pre-populates top-level collections, kept
    for backward compatibility with the original users-only fake.
    """

    def __init__(self, seed=None, **legacy_seed):
        self._root: dict[str, dict] = {}
        combined = dict(seed or {})
        combined.update(legacy_seed)
        for collection_name, docs in combined.items():
            store = self._root.setdefault(collection_name, {})
            for doc_id, data in docs.items():
                store[doc_id] = {"data": dict(data), "subcollections": {}}

    def collection(self, name):
        store = self._root.setdefault(name, {})
        return FakeCollection(store)


class FakeChatGraph:
    """
    Stand-in for the compiled LangGraph workflow (graph.workflow.app).
    Configure `.answer`, `.category`, `.token_usage`, or `.raise_exc` before
    making a request to control the outcome of POST /chats/{id}/messages.
    """

    def __init__(self, answer="Mocked AI reply", category="ifrs", raise_exc=None, token_usage=None):
        self.answer = answer
        self.category = category
        self.raise_exc = raise_exc
        self.token_usage = (
            token_usage
            if token_usage is not None
            else {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46}
        )
        self.last_invoke_state = None

    def invoke(self, state):
        self.last_invoke_state = state
        if self.raise_exc:
            raise self.raise_exc
        result = {"answer": self.answer}
        if self.category is not None:
            result["category"] = self.category
        if self.token_usage is not None:
            result["token_usage"] = self.token_usage
        return result

    def stream(self, state, stream_mode="updates"):
        """Mimics `app.stream(state, stream_mode="updates")`, yielding one
        {node_name: partial_state} dict per node, ending with the "generate"
        node's answer/category/token_usage. Raises `.raise_exc` (if set) on
        the first step, same as a real graph error partway through a run.
        """
        self.last_invoke_state = state
        if self.raise_exc:
            raise self.raise_exc
        yield {"router": {"intent": "retrieve", "category": self.category}}
        result = {"answer": self.answer}
        if self.category is not None:
            result["category"] = self.category
        if self.token_usage is not None:
            result["token_usage"] = self.token_usage
        yield {"generate": result}
