FROM python:3.13-alpine

RUN apk add --no-cache docker-cli docker-cli-compose

WORKDIR /autoscaler

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY autoscaler.py .

CMD ["python", "-u", "autoscaler.py"]
