# syntax=docker/dockerfile:1.7
#
# Full backend + ICH research model in ONE image (Stage 1 of the online deployment).
#
#   docker build -t agentic-medical-runtime \
#       --build-arg SKP_SOURCE="<pip-installable source of the external skp package>" .
#
# SKP_SOURCE is required: the ICH model imports the external `skp` research code, which is not in
# this repository and not on PyPI. Use a PUBLIC pip source (e.g. git+https://...@<commit>). Never pass
# a token in a build arg: build args are visible in the image history.
#
# CPU only on purpose: the ICH model measured ~27 s for 40x512x512 on a laptop CPU. GPU is a later,
# measured decision (see docs/ONLINE_RUNTIME.md).
#
# Research & Engineering Prototype - Not for clinical diagnosis or treatment.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- builder
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends git build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build

# 1. CPU PyTorch first, so the later `torch>=...` requirement is already satisfied and pip does not
#    pull the multi-GB CUDA build from PyPI.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --index-url "${TORCH_INDEX_URL}" "torch>=2.2"

# 2. Python dependencies. requirements-lock.txt is OPTIONAL: when present it constrains every version
#    (generate it from a known-good build, see docs/ONLINE_RUNTIME.md). The glob keeps the COPY valid
#    when the file does not exist yet.
COPY requirements.txt requirements-runtime.txt requirements-lock.tx[t] ./
RUN if [ -f requirements-lock.txt ]; then \
        pip install -c requirements-lock.txt -r requirements-runtime.txt; \
    else \
        pip install -r requirements-runtime.txt; \
    fi

# 3. The external research code the model imports. Fail early and clearly if it was not provided.
ARG SKP_SOURCE=""
RUN test -n "${SKP_SOURCE}" || { \
      echo "ERROR: build-arg SKP_SOURCE is required (pip-installable source of the external 'skp' package)." >&2; \
      exit 1; }
RUN pip install "${SKP_SOURCE}"

# 4. Fail the build if any required package is missing or broken.
COPY backend/ /build/backend/
COPY scripts/check_runtime.py scripts/prefetch_weights.py /build/scripts/
RUN python /build/scripts/check_runtime.py --imports-only

# 5. Optional: bake the model weights into the image (MIT licence on the model card). Baking removes
#    the network dependency and the cold-start download. Set PREFETCH_WEIGHTS=0 to skip (CI does).
ARG PREFETCH_WEIGHTS=1
ENV HF_HOME=/opt/model-cache
RUN mkdir -p /opt/model-cache
RUN if [ "${PREFETCH_WEIGHTS}" = "1" ]; then \
        python /build/scripts/prefetch_weights.py --manifest /opt/model-cache/model_manifest.json; \
    fi

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/model-cache /opt/model-cache

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/model-cache \
    PORT=8080

WORKDIR /app
COPY backend/ /app/backend/
COPY scripts/ /app/scripts/
COPY docker/entrypoint.sh /app/entrypoint.sh

# Uploads are written here until persistent object storage is added (Phase 3). This path is EPHEMERAL
# on every container platform; do not treat it as storage.
RUN mkdir -p /app/backend/uploads \
 && chmod +x /app/entrypoint.sh \
 && chown -R app:app /app /opt/model-cache

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8080'), timeout=4)"

ENTRYPOINT ["/app/entrypoint.sh"]
