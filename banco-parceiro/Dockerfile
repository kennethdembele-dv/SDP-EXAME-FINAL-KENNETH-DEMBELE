# Modulo legado em Java: compila com o JDK e corre so com o JRE (imagem mais pequena).
FROM eclipse-temurin:21-jdk-alpine AS compilar
WORKDIR /src
COPY src/BancoParceiro.java .
RUN javac -d /classes BancoParceiro.java

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=compilar /classes /app
RUN mkdir -p /dados
EXPOSE 8200
# Memoria limitada para caber num computador academico.
CMD ["java", "-Xmx64m", "-XX:+UseSerialGC", "-cp", "/app", "BancoParceiro"]
