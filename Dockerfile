ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-alpine as baseimg
WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements.txt /app/
RUN --mount=type=cache,target=/root/.cache\
    set -xe\
 && python -m pip install -U pip setuptools wheel\
 && python -m pip install -r /app/requirements.txt

FROM baseimg as production
VOLUME [ "/app/config" ]
ENTRYPOINT [ "gunicorn", "-k", "gevent", "main:create_app('/app/config/config.yml')" ]
CMD [ "-b", "[::]:8000" ]
EXPOSE 8000

FROM baseimg as buildenv
COPY *.py /app/
RUN set -xe\
 && python -m compileall /app -j 0 -b\
 && find /app -type f -name '*.py' -delete

FROM production
COPY --from=buildenv /app/ /app/