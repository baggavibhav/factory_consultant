# Factory Consultant: container image for hosting (Render, Azure, any Docker host).
# Stage 1 builds the LibreDWG converter (dwg2dxf) on Linux; stage 2 runs the app.

FROM python:3.12-slim AS libredwg
ARG LIBREDWG_VERSION=0.13.3
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl xz-utils ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl -fsSL "https://github.com/LibreDWG/libredwg/releases/download/${LIBREDWG_VERSION}/libredwg-${LIBREDWG_VERSION}.tar.xz" | tar -xJ \
 && cd "libredwg-${LIBREDWG_VERSION}" \
 && ./configure --disable-bindings --disable-docs --disable-python --prefix=/opt/libredwg \
 && make -j"$(nproc)" \
 && make install

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/libredwg/bin:$PATH \
    LD_LIBRARY_PATH=/opt/libredwg/lib \
    FCA_DWG2DXF=/opt/libredwg/bin/dwg2dxf \
    FCA_DATA_DIR=/data/projects \
    FCA_DEMO=1
COPY --from=libredwg /opt/libredwg /opt/libredwg
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
RUN pip install -e . && dwg2dxf --version
EXPOSE 8000
# Render (and most hosts) pass the port in $PORT.
CMD ["sh", "-c", "mkdir -p \"$FCA_DATA_DIR\" && exec fca serve --host 0.0.0.0 --port \"${PORT:-8000}\" --data \"$FCA_DATA_DIR\""]
