import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpsConfigurator;
import com.sun.net.httpserver.HttpsServer;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.KeyStore;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Pattern;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

/**
 * Banco parceiro (sistema legado simulado), escrito em Java so com a biblioteca padrao.
 *
 * Contrato XML sobre HTTPS (ver contrato.xsd):
 *   POST /legado/confirmacoes        recebe <confirmacaoTransferencia>, devolve <registoParceiro>
 *   GET  /legado/transferencias/{id} devolve <registoParceiro> ou <erro> (404)
 *   GET  /saude
 * Os registos ficam num ficheiro de texto (uma linha por confirmacao), relido no arranque.
 */
public class BancoParceiro {
    static final List<String> CAMPOS = List.of("id", "contaOrigem", "contaDestino", "montanteCentimos", "moeda", "concluidaEm");
    static final Map<String, Pattern> REGRAS = Map.of(
            "id", Pattern.compile("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
            "contaOrigem", Pattern.compile("^(EU|US)-\\d{4}$"),
            "contaDestino", Pattern.compile("^(EU|US)-\\d{4}$"),
            "montanteCentimos", Pattern.compile("^[1-9]\\d{0,14}$"),
            "moeda", Pattern.compile("^[A-Z]{3}$"));
    static final int MAXIMO_BYTES = 64 * 1024;

    /** Registos em memoria; ConcurrentHashMap porque varias threads atendem pedidos ao mesmo tempo. */
    static final Map<String, Map<String, String>> registos = new ConcurrentHashMap<>();
    static final AtomicLong sequencia = new AtomicLong();
    static Path ficheiro;

    public static void main(String[] args) throws Exception {
        int porta = Integer.parseInt(System.getenv().getOrDefault("PORTA", "8200"));
        ficheiro = Path.of(System.getenv().getOrDefault("FICHEIRO_REGISTOS", "/dados/registos.txt"));
        carregarRegistos();

        // TLS: certificado do laboratorio em PKCS#12 (gerado por seguranca/gerar_materiais.py).
        char[] senha = System.getenv().getOrDefault("KEYSTORE_SENHA", "laboratorio").toCharArray();
        KeyStore ks = KeyStore.getInstance("PKCS12");
        try (InputStream in = new FileInputStream(System.getenv().getOrDefault("KEYSTORE", "/run/secrets/banco-parceiro.p12"))) {
            ks.load(in, senha);
        }
        KeyManagerFactory kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        kmf.init(ks, senha);
        SSLContext tls = SSLContext.getInstance("TLS");
        tls.init(kmf.getKeyManagers(), null, null);

        HttpsServer servidor = HttpsServer.create(new InetSocketAddress(porta), 0);
        servidor.setHttpsConfigurator(new HttpsConfigurator(tls));
        servidor.createContext("/saude", t -> responder(t, 200, "<saude><estado>ok</estado><registos>" + registos.size() + "</registos></saude>"));
        servidor.createContext("/legado/confirmacoes", BancoParceiro::confirmar);
        servidor.createContext("/legado/transferencias/", BancoParceiro::consultar);
        servidor.setExecutor(Executors.newFixedThreadPool(4));   // 4 threads de atendimento
        servidor.start();
        System.out.println("Banco parceiro (Java " + Runtime.version() + ") a ouvir em HTTPS na porta " + porta
                + "; " + registos.size() + " registo(s) carregado(s)");
    }

    static void confirmar(HttpExchange t) throws IOException {
        try {
            if (!"POST".equals(t.getRequestMethod())) { erro(t, 405, "METODO", "use POST"); return; }
            byte[] corpo = t.getRequestBody().readNBytes(MAXIMO_BYTES + 1);
            if (corpo.length > MAXIMO_BYTES) { erro(t, 413, "DEMASIADO_GRANDE", "pedido acima de 64 KB"); return; }
            Map<String, String> pedido;
            try {
                pedido = lerPedido(corpo);
            } catch (IllegalArgumentException e) {
                System.out.println("Pedido recusado: " + e.getMessage());
                erro(t, 400, "DADOS_INVALIDOS", e.getMessage());
                return;
            }
            // Idempotente: a mesma transferencia devolve sempre o mesmo registo e a mesma referencia.
            boolean[] novo = {false};
            Map<String, String> registo = registos.computeIfAbsent(pedido.get("id"), id -> {
                novo[0] = true;
                Map<String, String> r = new LinkedHashMap<>();
                r.put("id", id);
                r.put("referenciaParceiro", String.format("BP-%06d", sequencia.incrementAndGet()));
                r.put("estado", "REGISTADA");
                for (String c : CAMPOS) if (!c.equals("id")) r.put(c, pedido.get(c));
                r.put("recebidaEm", Instant.now().toString());
                gravar(r);
                return r;
            });
            System.out.println((novo[0] ? "Confirmacao registada: " : "Confirmacao repetida: ") + registo.get("id")
                    + " -> " + registo.get("referenciaParceiro") + " (" + registo.get("montanteCentimos") + " centimos)");
            responder(t, novo[0] ? 201 : 200, xmlRegisto(registo));
        } catch (Exception e) {
            erro(t, 500, "ERRO_INTERNO", e.getClass().getSimpleName());
        }
    }

    static void consultar(HttpExchange t) throws IOException {
        String id = t.getRequestURI().getPath().substring("/legado/transferencias/".length());
        if (!REGRAS.get("id").matcher(id).matches()) { erro(t, 400, "DADOS_INVALIDOS", "id invalido"); return; }
        Map<String, String> r = registos.get(id);
        if (r == null) erro(t, 404, "DESCONHECIDA", "transferencia sem registo no banco parceiro");
        else responder(t, 200, xmlRegisto(r));
    }

    /** Le e valida o XML recebido. Recusa DTD e entidades externas (protecao contra XXE). */
    static Map<String, String> lerPedido(byte[] corpo) {
        Document doc;
        try {
            DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
            f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            f.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            f.setXIncludeAware(false);
            f.setExpandEntityReferences(false);
            var leitor = f.newDocumentBuilder();
            leitor.setErrorHandler(null);          // o erro e devolvido ao cliente, nao impresso
            doc = leitor.parse(new ByteArrayInputStream(corpo));
        } catch (Exception e) {
            throw new IllegalArgumentException("XML mal formado: " + e.getMessage());
        }
        Element raiz = doc.getDocumentElement();
        if (!"confirmacaoTransferencia".equals(raiz.getTagName()))
            throw new IllegalArgumentException("elemento raiz esperado: confirmacaoTransferencia");
        if (!"1".equals(raiz.getAttribute("versao")))
            throw new IllegalArgumentException("versao do contrato nao suportada");
        Map<String, String> dados = new LinkedHashMap<>();
        for (Node n = raiz.getFirstChild(); n != null; n = n.getNextSibling())
            if (n instanceof Element e) dados.put(e.getTagName(), e.getTextContent().trim());
        for (String c : CAMPOS) {
            String v = dados.get(c);
            if (v == null || v.isEmpty()) throw new IllegalArgumentException("falta o campo " + c);
            Pattern p = REGRAS.get(c);
            if (p != null && !p.matcher(v).matches()) throw new IllegalArgumentException("campo " + c + " invalido: " + v);
        }
        if (dados.get("contaOrigem").equals(dados.get("contaDestino")))
            throw new IllegalArgumentException("origem e destino iguais");
        try {
            Instant.parse(dados.get("concluidaEm"));
        } catch (Exception e) {
            throw new IllegalArgumentException("concluidaEm nao e uma data ISO-8601 em UTC");
        }
        return dados;
    }

    static String xmlRegisto(Map<String, String> r) {
        StringBuilder sb = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<registoParceiro versao=\"1\">");
        r.forEach((k, v) -> sb.append('<').append(k).append('>').append(escapar(v)).append("</").append(k).append('>'));
        return sb.append("</registoParceiro>").toString();
    }

    static void erro(HttpExchange t, int codigo, String tipo, String mensagem) throws IOException {
        responder(t, codigo, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<erro><codigo>" + tipo + "</codigo><mensagem>"
                + escapar(mensagem) + "</mensagem></erro>");
    }

    static void responder(HttpExchange t, int codigo, String xml) throws IOException {
        byte[] b = xml.getBytes(StandardCharsets.UTF_8);
        t.getResponseHeaders().set("Content-Type", "application/xml; charset=utf-8");
        t.getResponseHeaders().set("X-Servico", "banco-parceiro-java");
        t.sendResponseHeaders(codigo, b.length);
        try (OutputStream os = t.getResponseBody()) { os.write(b); }
    }

    static String escapar(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }

    // ------------------------------------------------ persistencia simples (ficheiro de texto)
    static synchronized void gravar(Map<String, String> r) {
        StringBuilder linha = new StringBuilder();
        r.forEach((k, v) -> linha.append(k).append('=').append(v).append(';'));
        try {
            Files.createDirectories(ficheiro.getParent());
            Files.writeString(ficheiro, linha + "\n", StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND, StandardOpenOption.SYNC);
        } catch (IOException e) {
            throw new RuntimeException("nao foi possivel gravar o registo", e);
        }
    }

    static void carregarRegistos() throws IOException {
        if (!Files.exists(ficheiro)) return;
        for (String linha : Files.readAllLines(ficheiro, StandardCharsets.UTF_8)) {
            if (linha.isBlank()) continue;
            Map<String, String> r = new LinkedHashMap<>();
            for (String par : linha.split(";")) {
                int i = par.indexOf('=');
                if (i > 0) r.put(par.substring(0, i), par.substring(i + 1));
            }
            registos.put(r.get("id"), r);
            sequencia.set(Math.max(sequencia.get(), Long.parseLong(r.get("referenciaParceiro").substring(3))));
        }
    }
}
