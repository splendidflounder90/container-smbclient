FROM python:3.14-alpine

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY client.py /client.py


ENTRYPOINT ["python","./client.py"]
