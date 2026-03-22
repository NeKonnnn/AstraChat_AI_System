FROM astrachat-base-ml:latest

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.11 -m pip install --prefer-binary --timeout 300 --retries 10 -r requirements.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=8 \
    OPENBLAS_NUM_THREADS=8 \
    MKL_NUM_THREADS=8

COPY app/ ./app/
COPY config/ ./config/

RUN mkdir -p /app/models/silero && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app/models

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
