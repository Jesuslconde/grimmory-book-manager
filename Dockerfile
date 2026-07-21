FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data
EXPOSE 80
ARG APP_VERSION
ENV VERSION=${APP_VERSION}
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
