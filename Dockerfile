FROM python:3.13.6-alpine3.21

ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

ENV TZ="America/Sao_Paulo"

# Copiar código do projeto
COPY ./emprestimos ./emprestimos

WORKDIR /emprestimos

# Tudo em um único RUN (como na versão original)
RUN pip install --upgrade pip && \
  pip install uv && \
  uv pip install --system -r pyproject.toml && \
  mkdir -p /emprestimos/static && \
  adduser --disabled-password --no-create-home duser && \
  chown -R duser:duser /emprestimos/static

USER duser