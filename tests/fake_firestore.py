"""
Firestore en memoria para las pruebas de la Clínica Odontológica.

Imita lo que usa FirebaseAdapter: collection/document/get/set/update/delete, subcolecciones,
where(... "==" ...), limit, stream, collection_group y transacciones. La transacción
aplica sus escrituras al final (como Firestore) y exige que todas las lecturas vayan
antes de la primera escritura; si una lectura llega tarde, la prueba falla.
"""

import copy


class _Snap:
    def __init__(self, ref, data):
        self.reference, self.id = ref, ref.id
        self._data = copy.deepcopy(data)

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class _Doc:
    def __init__(self, db, path):
        self._db, self.path = db, path
        self.id = path.split("/")[-1]

    def get(self, transaction=None, timeout=None):
        if transaction is not None:
            transaction._leer()
        return _Snap(self, self._db._datos.get(self.path))

    def set(self, data):
        self._db._datos[self.path] = copy.deepcopy(data)

    def update(self, cambios):
        if self.path not in self._db._datos:
            raise KeyError(f"No existe {self.path}")
        doc = self._db._datos[self.path]
        for clave, valor in cambios.items():
            partes, d = clave.split("."), doc
            for p in partes[:-1]:
                d = d.setdefault(p, {})
            d[partes[-1]] = copy.deepcopy(valor)

    def delete(self):
        self._db._datos.pop(self.path, None)

    def collection(self, nombre):
        return _Col(self._db, f"{self.path}/{nombre}")

    def collections(self):
        pref = self.path + "/"
        nombres = {k[len(pref):].split("/")[0] for k in self._db._datos if k.startswith(pref)}
        return [self.collection(n) for n in nombres]


class _Query:
    def __init__(self, db, filtro, filtros=(), tope=None):
        self._db, self._filtro, self._filtros, self._tope = db, filtro, list(filtros), tope

    def where(self, campo, op, valor):
        assert op == "==", "el fake solo soporta =="
        return _Query(self._db, self._filtro, self._filtros + [(campo, valor)], self._tope)

    def limit(self, n):
        return _Query(self._db, self._filtro, self._filtros, n)

    def stream(self):
        salida = []
        for path in sorted(self._db._datos):
            if self._filtro(path) and all(self._db._datos[path].get(c) == v for c, v in self._filtros):
                salida.append(_Snap(_Doc(self._db, path), self._db._datos[path]))
        return salida[: self._tope] if self._tope else salida

    def get(self, transaction=None):
        if transaction is not None:
            transaction._leer()
        return self.stream()


class _Col(_Query):
    def __init__(self, db, path):
        self.path = path
        super().__init__(db, lambda p: p.rsplit("/", 1)[0] == path)

    def document(self, doc_id):
        return _Doc(self._db, f"{self.path}/{doc_id}")


class _Tx:
    def __init__(self):
        self._ops, self._escribio = [], False

    def _leer(self):
        assert not self._escribio, "Firestore exige leer antes de escribir en una transacción"

    def set(self, ref, data):
        self._escribio = True
        self._ops.append(lambda: ref.set(data))

    def update(self, ref, cambios):
        self._escribio = True
        self._ops.append(lambda: ref.update(cambios))

    def delete(self, ref):
        self._escribio = True
        self._ops.append(lambda: ref.delete())

    def commit(self):
        for op in self._ops:
            op()


class FakeFirestore:
    def __init__(self):
        self._datos = {}

    def collection(self, nombre):
        return _Col(self, nombre)

    def collection_group(self, nombre):
        return _Query(self, lambda p: p.split("/")[-2] == nombre)

    def batch(self):
        return _Tx()

    def run_tx(self, fn):
        tx = _Tx()
        resultado = fn(tx)          # si fn lanza, nada se escribe
        tx.commit()
        return resultado


def adaptador_odontologia():
    """FirebaseAdapter sobre el Firestore en memoria, con los datos de init_odontologia.json."""
    import json
    import os

    from src.infrastructure.adapters.firebase_adapter import FirebaseAdapter
    from src.infrastructure.config import Config

    db = FakeFirestore()
    raiz = os.path.join(os.path.dirname(__file__), "..", "database", "firebase")
    with open(os.path.join(raiz, "init_odontologia.json"), encoding="utf-8") as f:
        data = json.load(f)
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_firestore", os.path.join(raiz, "seed_firestore.py"))
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    seed.cargar(db, data)

    config = Config()
    config.FIRESTORE_EMULATOR_HOST = ""
    adapter = FirebaseAdapter(config, client=db)
    adapter._run_tx = db.run_tx
    return adapter
