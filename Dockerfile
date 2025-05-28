FROM python:3.13-slim

RUN  pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "livepeer.py"]
