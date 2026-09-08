FROM python:3.12-slim
RUN pip install --no-cache-dir "psycopg[binary]"
COPY collect.py /app/collect.py
CMD ["python", "/app/collect.py"]
