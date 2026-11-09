#!/bin/sh
# Emulador de Firestore con datos persistentes en el volumen /firebase/datos.
#
# El emulador guarda todo en memoria. Para no perder los datos:
#   * al apagarse bien (docker compose stop/down) exporta a /firebase/datos/actual;
#   * además hace un respaldo cada 2 minutos, por si Docker Desktop o la
#     computadora se cierran sin apagar el contenedor.
# El respaldo se escribe primero en "nuevo" y luego se cambia de nombre, para
# que un corte a la mitad nunca deje una copia dañada.
PROYECTO=clinica-odontologica-landivar
DATOS=/firebase/datos
mkdir -p "$DATOS"

IMPORTAR=""
for d in "$DATOS/actual" "$DATOS/anterior" "$DATOS"; do
  if [ -f "$d/firebase-export-metadata.json" ]; then IMPORTAR="--import=$d"; break; fi
done
echo "Datos a importar: ${IMPORTAR:-ninguno (base nueva)}"

firebase emulators:start --only firestore --project "$PROYECTO" $IMPORTAR --export-on-exit="$DATOS/actual" &
PID=$!
trap 'kill -TERM $PID; wait $PID; exit 0' TERM INT

(
  sleep 90
  while kill -0 $PID 2>/dev/null; do
    rm -rf "$DATOS/nuevo"
    if firebase emulators:export "$DATOS/nuevo" --force --project "$PROYECTO" >/dev/null 2>&1; then
      rm -rf "$DATOS/anterior"
      [ -d "$DATOS/actual" ] && mv "$DATOS/actual" "$DATOS/anterior"
      mv "$DATOS/nuevo" "$DATOS/actual"
    fi
    sleep 120
  done
) &

wait $PID
