"""Gera os materiais de seguranca do laboratorio (nunca vao para o Git).

    python seguranca/gerar_materiais.py

Cria a pasta segredos/ com:
  ca.crt                      autoridade certificadora do laboratorio (instalar como confianca)
  ca-privada/ca.key           chave da CA: so serve para assinar; nao e montada em nenhum contentor
  <servico>.crt / .key        certificado TLS de cada servico, com o nome DNS no SAN
  banco-parceiro.p12          o mesmo certificado em PKCS#12, para o Java
  jwt-privada.pem             so o servico de autenticacao a monta (assina os tokens)
  jwt-publica.pem             as APIs validam os tokens com esta chave, sem falar com a autenticacao
  assinatura-api-N.pem        chave privada com que a instancia N da API assina as ordens de transferencia
  assinatura-api-N.pub.pem    chave publica correspondente, usada pelo coordenador para verificar
E cria .env com palavras-passe aleatorias, se ainda nao existir.

Para os dois computadores: gerar UMA vez e copiar a pasta segredos/ e o .env para o outro PC
(os nomes DNS sao os mesmos nos dois modos; ver docs/DOIS_COMPUTADORES.md).
"""
import datetime as dt
import ipaddress
import secrets
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "segredos"
# Nome DNS de cada servico (o mesmo na rede Docker e no ficheiro hosts dos dois computadores).
SERVICOS = ["auth", "api-1", "api-2", "coordenador", "banco-parceiro",
            "db-europa", "db-america", "db-coordenador"]
PALAVRA_PASSE_P12 = "laboratorio"   # so protege o ficheiro PKCS#12 em transito; documentado no README


def chave_rsa(bits=2048):
    return rsa.generate_private_key(public_exponent=65537, key_size=bits)


def gravar_chave(chave, caminho):
    caminho.write_bytes(chave.private_bytes(serialization.Encoding.PEM,
                                            serialization.PrivateFormat.PKCS8,
                                            serialization.NoEncryption()))


def gravar_publica(chave, caminho):
    caminho.write_bytes(chave.public_key().public_bytes(serialization.Encoding.PEM,
                                                        serialization.PublicFormat.SubjectPublicKeyInfo))


def criar_ca():
    chave = chave_rsa(3072)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Global-Scale Laboratorio CA")])
    agora = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome)
            .public_key(chave.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(agora - dt.timedelta(minutes=5))
            .not_valid_after(agora + dt.timedelta(days=825))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                         content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .sign(chave, hashes.SHA256()))
    return chave, cert


def criar_certificado(nome_dns, ca_chave, ca_cert):
    chave = chave_rsa()
    agora = dt.datetime.now(dt.timezone.utc)
    # SAN: o nome do servico (verificado pelos clientes) e localhost (testes no proprio PC).
    san = x509.SubjectAlternativeName([x509.DNSName(nome_dns), x509.DNSName("localhost"),
                                       x509.IPAddress(ipaddress.ip_address("127.0.0.1"))])
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome_dns)]))
            .issuer_name(ca_cert.subject).public_key(chave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(agora - dt.timedelta(minutes=5))
            .not_valid_after(agora + dt.timedelta(days=397))
            .add_extension(san, critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH,
                                                  ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .sign(ca_chave, hashes.SHA256()))
    return chave, cert


def criar_env():
    env = RAIZ / ".env"
    if env.exists():
        print("  .env ja existe: mantido")
        return
    modelo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    linhas = []
    for linha in modelo.splitlines():
        if "=" in linha and linha.split("=", 1)[1].strip() == "trocar":
            linha = linha.split("=", 1)[0] + "=" + secrets.token_urlsafe(18)
        linhas.append(linha)
    env.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("  .env criado com palavras-passe aleatorias")


def main():
    if (SAIDA / "ca.crt").exists() and "--forcar" not in sys.argv:
        print("segredos/ ja existe. Use --forcar para gerar tudo de novo.")
        criar_env()
        return
    (SAIDA / "ca-privada").mkdir(parents=True, exist_ok=True)
    ca_chave, ca_cert = criar_ca()
    gravar_chave(ca_chave, SAIDA / "ca-privada" / "ca.key")
    (SAIDA / "ca.crt").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    print("  CA criada")

    for s in SERVICOS:
        chave, cert = criar_certificado(s, ca_chave, ca_cert)
        gravar_chave(chave, SAIDA / f"{s}.key")
        (SAIDA / f"{s}.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        if s == "banco-parceiro":   # o Java le PKCS#12 directamente (KeyStore "PKCS12")
            p12 = pkcs12.serialize_key_and_certificates(
                b"banco-parceiro", chave, cert, [ca_cert],
                serialization.BestAvailableEncryption(PALAVRA_PASSE_P12.encode()))
            (SAIDA / "banco-parceiro.p12").write_bytes(p12)
    print("  certificados TLS:", ", ".join(SERVICOS))

    jwt = chave_rsa()
    gravar_chave(jwt, SAIDA / "jwt-privada.pem")
    gravar_publica(jwt, SAIDA / "jwt-publica.pem")
    print("  par de chaves JWT (RS256)")

    for n in (1, 2):
        k = chave_rsa()
        gravar_chave(k, SAIDA / f"assinatura-api-{n}.pem")
        gravar_publica(k, SAIDA / f"assinatura-api-{n}.pub.pem")
    print("  chaves de assinatura das ordens: api-1, api-2")
    criar_env()
    print(f"Materiais em {SAIDA}")


if __name__ == "__main__":
    main()
