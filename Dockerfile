FROM arm32v7/debian:bookworm
COPY . /openeo
ENTRYPOINT /openeo/openeo.py