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
# Arranque con respaldo automático de los datos (ver iniciar_emulador.sh).
# El sed quita los finales de línea de Windows por si git los convirtió.
COPY iniciar_emulador.sh ./
RUN sed -i 's/\r$//' iniciar_emulador.sh && chmod +x iniciar_emulador.sh
CMD ["./iniciar_emulador.sh"]
