# Image tout-en-un : Python, ffmpeg et les polices.
# Rien à installer sur ta machine à part Docker.
FROM python:3.12-slim

# ffmpeg fait le montage et toutes les mesures (coupes, son, images-clés),
# libass incruste les sous-titres, les polices DejaVu servent au karaoké.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Les dépendances d'abord, le code ensuite : modifier une ligne de Python ne
# doit pas relancer l'installation de numpy.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        typer rich httpx pydantic pydantic-settings PyYAML jinja2 \
        jsonschema fastapi "uvicorn[standard]" python-multipart \
        pillow numpy

COPY pdz/ ./pdz/
COPY tools/ ./tools/
COPY univers/ ./univers/
COPY modeles.yaml ./

# Installe le paquet sans retoucher aux dépendances déjà en place : c'est ce
# qui rend la commande `pdz` disponible telle quelle dans le conteneur.
RUN pip install --no-cache-dir --no-deps -e .

# Les données restent sur ta machine, pas dans l'image.
VOLUME ["/app/donnees"]

ENV PYTHONUNBUFFERED=1
CMD ["pdz", "cles"]
