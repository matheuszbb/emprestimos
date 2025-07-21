FROM python:3.12-alpine3.19

ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

ENV TZ="America/Sao_Paulo"

COPY ./emprestimos ./emprestimos

WORKDIR /emprestimos

RUN python -m venv /venv && \
  /venv/bin/pip install --upgrade pip && \
  /venv/bin/pip install -r /emprestimos/requirements.txt && \
  mkdir -p /emprestimos/static && \
  adduser --disabled-password --no-create-home duser && \
  chown -R duser:duser /emprestimos/static && \
  chown -R duser:duser /venv

USER duser