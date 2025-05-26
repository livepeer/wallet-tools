FROM python:3.11-slim

# Set working directory
WORKDIR /app

RUN  pip install web3 \
  && pip install eth-utils \
  && pip install setuptools

COPY . .

# Default command (replace main.py with your entrypoint if different)
CMD ["python", "OrchestratorSiphon.py"]