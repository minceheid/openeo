FROM arm32v5/debian:bookworm
COPY . /openeo
RUN apt-get update && apt-get install -y python3-serial python3-websockets python3-jsonschema python3-jinja2 python3-rpi.gpio && apt clean
ENTRYPOINT python3 /openeo/openeo.py