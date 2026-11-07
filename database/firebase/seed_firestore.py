"""
Carga los datos iniciales de la Clínica Odontológica en Cloud Firestore.

Funciona contra el emulador local (FIRESTORE_EMULATOR_HOST) o contra un proyecto
real de Firebase (FIREBASE_CREDENTIALS_PATH). Lee la configuración del archivo .env.

Uso (desde la raíz del proyecto):
    python database/firebase/seed_firestore.py            # carga / sobrescribe
    python database/firebase/seed_firestore.py --limpiar  # borra todo y vuelve a cargar
"""

import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from src.infrastructure.config import Config  # noqa: E402
from src.infrastructure.adapters.firebase_adapter import crear_cliente_firestore  # noqa: E402

COLECCIONES = ["pacientes", "citas", "odontologos", "secretarias", "procedimientos_catalogo",
               "contadores", "dpi_index", "colegiado_index"]


def borrar_coleccion(col):
    for doc in col.stream():
        for sub in doc.reference.collections():
            borrar_coleccion(sub)
        doc.reference.delete()


def main():
    config = Config()
    db = crear_cliente_firestore(config)
    destino = (f"emulador {config.FIRESTORE_EMULATOR_HOST}" if config.FIRESTORE_EMULATOR_HOST
               else f"proyecto {config.FIREBASE_PROJECT_ID}")
    print(f"Conectado a Firestore ({destino})")

    if "--limpiar" in sys.argv:
        for nombre in COLECCIONES:
            borrar_coleccion(db.collection(nombre))
        print("Colecciones borradas.")
    elif db.collection("contadores").document("pacientes").get().exists:
        # Volver a cargar reiniciaría los contadores y los pacientes nuevos se sobrescribirían.
        print("Firestore ya tiene datos; no se cargó nada. Use --limpiar para borrar y volver a cargar.")
        return

    with open(os.path.join(os.path.dirname(__file__), "init_odontologia.json"), encoding="utf-8") as f:
        data = json.load(f)

    batch = db.batch()
    for p in data["procedimientos_catalogo"]:
        batch.set(db.collection("procedimientos_catalogo").document(str(p["id_procedimiento"])), p)
    for o in data["odontologos"]:
        batch.set(db.collection("odontologos").document(str(o["id_odontologo"])), o)
        batch.set(db.collection("colegiado_index").document(o["numero_colegiado"]), {"id_odontologo": o["id_odontologo"]})
    for s in data["secretarias"]:
        batch.set(db.collection("secretarias").document(str(s["id_secretaria"])), s)
    for c in data["citas"]:
        batch.set(db.collection("citas").document(str(c["id_cita"])), c)
    for nombre, seq in data["contadores"].items():
        batch.set(db.collection("contadores").document(nombre), {"seq": seq})
    for p in data["pacientes"]:
        consultas = p.pop("consultas", [])
        ref = db.collection("pacientes").document(str(p["id_paciente"]))
        batch.set(ref, p)
        batch.set(db.collection("dpi_index").document(p["dpi"]), {"id_paciente": p["id_paciente"]})
        for c in consultas:
            batch.set(ref.collection("consultas").document(str(c["id_consulta"])), c)
    batch.commit()  # un batch es atómico: se carga todo o nada

    print(f"Listo: {len(data['pacientes'])} pacientes, {len(data['citas'])} citas, "
          f"{len(data['procedimientos_catalogo'])} procedimientos en catálogo.")


if __name__ == "__main__":
    main()
