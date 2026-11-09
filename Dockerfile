FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends baresip-core iproute2 python3 python3-msgpack && rm -rf /var/lib/apt/lists/*
COPY gateway.py /opt/gateway.py
CMD ["python3", "-u", "/opt/gateway.py"]
