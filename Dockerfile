FROM lachlanevenson/k8s-kubectl

RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip

COPY . /

RUN pip3 install --upgrade pip setuptools && \
    pip3 install -r /requirements.txt && \
    rm -r /root/.cache

ENTRYPOINT ["python3", "/end2end_k8s.py"]
CMD ["--help"]
