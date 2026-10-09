FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 FITTAG_FEEDBACK=/tmp/fittag-feedback.jsonl
WORKDIR /app
COPY requirements-render.txt ./
RUN pip install --no-cache-dir -r requirements-render.txt
COPY core ./core
COPY api ./api
COPY viz ./viz
COPY adapters ./adapters
COPY measure.py ./
COPY web ./web
COPY tools/download_depth_model.py ./tools/download_depth_model.py
COPY third_party ./third_party
RUN python -m tools.download_depth_model models/metric-small.onnx
ENV FITTAG_DEPTH_MODEL=/app/models/metric-small.onnx
RUN useradd --create-home fittag
USER fittag
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
