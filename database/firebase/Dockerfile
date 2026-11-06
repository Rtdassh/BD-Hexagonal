# Emulador local de Cloud Firestore (Clínica Odontológica)
FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g firebase-tools@13

WORKDIR /firebase
COPY firebase.json firestore.rules ./

# Descarga el emulador y la interfaz web dentro de la imagen
RUN firebase setup:emulators:firestore && firebase setup:emulators:ui

EXPOSE 8080 4000
# Los datos se guardan en /firebase/datos al apagar el contenedor y se vuelven a importar al iniciar.
CMD ["sh", "-c", "mkdir -p /firebase/datos && if [ -f /firebase/datos/firebase-export-metadata.json ]; then IMP=--import=/firebase/datos; fi; exec firebase emulators:start --only firestore --project clinica-odontologica-landivar $IMP --export-on-exit=/firebase/datos"]
