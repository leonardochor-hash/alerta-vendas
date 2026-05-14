import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Configuracoes ───────────────────────────────────────────────
MOOMBOX_URL      = "https://expositores.moombox.com.br"
USUARIO          = "moombox"
SENHA            = "admin2020b"

EMAIL_REMETENTE     = os.environ.get("EMAIL_REMETENTE", "cap00leonardo@gmail.com")
EMAIL_DESTINATARIO  = os.environ.get("EMAIL_DESTINATARIO", "leonardochor@gmail.com")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")

DATA_SIMULADA = os.environ.get("DATA_SIMULADA", "")
HORA_SIMULADA = os.environ.get("HORA_SIMULADA", "")
MIN_SIMULADA  = os.environ.get("MIN_SIMULADA", "")

CONTADOR_FILE = "contadores.json"

# Valor minimo para a transacao ser considerada como venda valida
VALOR_MINIMO = 80.0

LOJAS = {
    "1": "Rio Sul",
    "3": "Barra Shopping",
    "4": "NorteShopping"
}

INSTRUCOES = [
    "Verifique se o terminal esta ligado e com sinal.",
    "Confira se ha clientes sendo atendidos no momento.",
    "Verifique se o sistema de pagamento esta funcionando.",
    "Entre em contato com a equipe da loja imediatamente.",
    "Verifique se ha problema tecnico no sistema de vendas.",
]

# ─── Sessao HTTP ──────────────────────────────────────────────────
def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    return s

session = make_session()

def login():
    try:
        r = session.get(MOOMBOX_URL + "/user/login", timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        csrf_tag = soup.find("input", {"name": "_csrf"})
        if not csrf_tag:
            print("ERRO: csrf nao encontrado")
            return False
        csrf = csrf_tag["value"]
        resp = session.post(MOOMBOX_URL + "/user/login", data={
            "_csrf": csrf,
            "login-form[login]": USUARIO,
            "login-form[password]": SENHA,
            "login-form[rememberMe]": "0",
        }, timeout=30)
        if "logout" in resp.text.lower():
            print("Login OK")
            return True
        print("AVISO: Login pode ter falhado")
        return False
    except Exception as e:
        print(f"ERRO login: {e}")
        return False

# ─── Busca vendas nos ultimos 60 minutos ─────────────────────────
def buscar_vendas_recentes(data_str, hora_inicio, minuto_inicio, hora_fim, minuto_fim):
    """
    Busca transacoes succeeded do dia, filtrando pela janela de tempo
    e apenas transacoes com valor_op > VALOR_MINIMO.

    Estrutura da tabela:
    - Linha 17 colunas: col[0]=seq, col[1]=loja_id (ou "Total"),
                        col[2]=cod_auth, col[3]=data_hora,
                        col[4]=valor, col[5]=valor_op
    - Linha 16 colunas: col[0]=seq, col[1]=cod_auth, col[2]=data_hora,
                        col[3]=valor, col[4]=valor_op
    current_loja so muda quando linha tem 17 colunas E col[1] nao e "Total"
    """
    data_enc = data_str + " - " + data_str
    params = {
        "TransacaoPosSearch[data]": data_enc,
        "TransacaoPosSearch[status]": "succeeded",
        "TransacaoPosSearch[authorization_code]": "",
        "TransacaoPosSearch[tipo_pagamento]": "",
        "TransacaoPosSearch[entry_mode]": "",
        "TransacaoPosSearch[id_zoop]": "",
    }
    resultado = {loja_id: {"total": 0.0, "count": 0} for loja_id in LOJAS}
    inicio_min = hora_inicio * 60 + minuto_inicio
    fim_min    = hora_fim    * 60 + minuto_fim

    try:
        r = session.get(MOOMBOX_URL + "/zoop/financeiro", params=params, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        current_loja = None
        for row in soup.select("table tbody tr"):
            cells = row.find_all("td")
            if len(cells) == 17:
                loja_candidata = cells[1].get_text(strip=True)
                if loja_candidata and loja_candidata != "Total":
                    current_loja = loja_candidata
                data_hora = cells[3].get_text(strip=True)
                valor_op  = cells[5].get_text(strip=True)
            elif len(cells) == 16:
                if cells[1].get_text(strip=True) == "Total":
                    continue
                data_hora = cells[2].get_text(strip=True)
                valor_op  = cells[4].get_text(strip=True)
            else:
                continue

            if current_loja not in LOJAS:
                continue

            # Filtrar janela de tempo
            try:
                partes = data_hora.split(" ")[1].split(":")
                h = int(partes[0])
                m = int(partes[1])
                t_min = h * 60 + m
                if not (inicio_min <= t_min < fim_min):
                    continue
            except:
                continue

            try:
                valor = float(valor_op.replace(",", "."))
                # Apenas transacoes acima do valor minimo
                if valor <= VALOR_MINIMO:
                    print(f"  [ignorado] {current_loja} R$ {valor:.2f} <= R$ {VALOR_MINIMO:.2f}")
                    continue
                resultado[current_loja]["total"] += valor
                resultado[current_loja]["count"] += 1
            except:
                pass

    except Exception as e:
        print(f"ERRO buscar Zoop {data_str}: {e}")

    return resultado

# ─── Contadores persistidos ───────────────────────────────────────
def carregar_contadores():
    if os.path.exists(CONTADOR_FILE):
        try:
            with open(CONTADOR_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def salvar_contadores(contadores):
    with open(CONTADOR_FILE, "w") as f:
        json.dump(contadores, f, indent=2)

# ─── Email ────────────────────────────────────────────────────────
def enviar_email(assunto, corpo_texto, corpo_html=None):
    if not GMAIL_APP_PASSWORD:
        print("Email ignorado: GMAIL_APP_PASSWORD nao configurado.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = EMAIL_REMETENTE
        msg["To"]      = EMAIL_DESTINATARIO
        msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))
        if corpo_html:
            msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(EMAIL_REMETENTE, GMAIL_APP_PASSWORD)
            smtp.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
        print(f"Email enviado: {assunto}")
    except Exception as e:
        print(f"ERRO email: {e}")

def montar_html(texto):
    import html as hl
    return (
        "<html><body style='font-family:Arial,sans-serif;font-size:14px;'>"
        "<div style='background:#fff3cd;border:2px solid #ff9800;border-radius:8px;padding:20px;max-width:600px;'>"
        + hl.escape(texto).replace("\n", "<br>")
        + "</div></body></html>"
    )

# ─── Logica principal ─────────────────────────────────────────────
def normalizar_hora(h_str):
    h_str = h_str.strip()
    return h_str + ":00" if ":" not in h_str else h_str

def main():
    if DATA_SIMULADA:
        hora_str = normalizar_hora(HORA_SIMULADA) if HORA_SIMULADA else "13:00"
        agora_br = datetime.strptime(DATA_SIMULADA + " " + hora_str, "%d/%m/%Y %H:%M")
        if MIN_SIMULADA:
            agora_br = agora_br.replace(minute=int(MIN_SIMULADA.strip()))
    else:
        import pytz
        tz_br = pytz.timezone("America/Sao_Paulo")
        agora_br = datetime.now(tz_br).replace(tzinfo=None)

    hora_atual = agora_br.hour
    min_atual  = agora_br.minute

    # Horario comercial: 11h-22h
    if not (11 <= hora_atual <= 22):
        print(f"Fora do horario comercial ({hora_atual}h). Nada enviado.")
        return

    data_str = agora_br.strftime("%d/%m/%Y")

    # Janela: ultima hora (roda de hora em hora no minuto 00)
    inicio = agora_br - timedelta(hours=1)
    hora_ini = inicio.hour
    min_ini  = inicio.minute
    if inicio.date() < agora_br.date():
        hora_ini = 0
        min_ini  = 0

    print(f"Verificando vendas > R$ {VALOR_MINIMO:.0f}: {data_str} {hora_ini:02d}:{min_ini:02d} ate {hora_atual:02d}:{min_atual:02d}")

    if not login():
        print("ERRO: Login falhou. Abortando.")
        return

    vendas = buscar_vendas_recentes(data_str, hora_ini, min_ini, hora_atual, min_atual)
    contadores = carregar_contadores()

    for loja_id, loja_nome in LOJAS.items():
        total = vendas[loja_id]["total"]
        count = vendas[loja_id]["count"]
        print(f"{loja_nome} (loja {loja_id}): {count} vendas validas | R$ {total:.2f} na ultima hora")

        chave = f"alerta_{loja_id}"
        if count == 0:
            contadores[chave] = contadores.get(chave, 0) + 1
            qtd = contadores[chave]
            horas_sem_venda = qtd
            instrucao = INSTRUCOES[min(qtd - 1, len(INSTRUCOES) - 1)]

            if horas_sem_venda == 1:
                tempo_str = "1 hora"
            else:
                tempo_str = f"{horas_sem_venda} horas"

            assunto = f"ALERTA [{loja_nome}] Sem vendas ha {tempo_str} (alerta #{qtd})"
            corpo = (
                f"ALERTA DE INATIVIDADE DE VENDAS\n"
                f"{'=' * 45}\n"
                f"Loja:             {loja_nome}\n"
                f"Sem vendas ha:    {tempo_str} (vendas > R$ {VALOR_MINIMO:.0f})\n"
                f"Numero do alerta: #{qtd}\n"
                f"Horario:          {data_str} {hora_atual:02d}:{min_atual:02d}\n"
                f"{'=' * 45}\n"
                f"\nACAO NECESSARIA:\n{instrucao}\n"
                f"\nFavor verificar imediatamente!\n"
            )
            print(f"  -> ALERTA #{qtd}: {loja_nome} sem vendas validas ha {tempo_str}")
            enviar_email(assunto, corpo, montar_html(corpo))
        else:
            if contadores.get(chave, 0) > 0:
                print(f"  -> {loja_nome} voltou a vender! Resetando contador (estava em {contadores[chave]}).")
            contadores[chave] = 0

    salvar_contadores(contadores)
    print("Contadores:", contadores)

if __name__ == "__main__":
    main()
