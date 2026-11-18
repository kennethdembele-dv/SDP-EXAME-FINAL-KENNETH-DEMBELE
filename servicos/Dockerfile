# Imagem comum aos servicos Python. O argumento SERVICO escolhe a pasta (autenticacao, api, coordenador).
FROM python:3.12.16-slim
WORKDIR /app
COPY servicos/requisitos.txt .
RUN pip install --no-cache-dir -r requisitos.txt
COPY servicos/comum/ /app/comum/
# O argumento so aparece aqui, para as camadas de cima serem partilhadas pelos tres servicos.
ARG SERVICO
ENV SERVICO=${SERVICO} PYTHONUNBUFFERED=1
COPY servicos/${SERVICO}/ /app/${SERVICO}/
CMD ["sh", "-c", "exec python -m ${SERVICO}.main"]
