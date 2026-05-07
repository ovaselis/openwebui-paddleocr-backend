FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
COPY requirements-paddle.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-paddle.txt

COPY app ./app

EXPOSE 9713

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9713"]