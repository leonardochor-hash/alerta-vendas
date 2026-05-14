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

# ─── Busca vendas na hora anterior completa ───────────────────────
def buscar_vendas_hora_anterior(data_str, hora_atual):
    """
    Verifica se houve venda valida (valor > VALOR_MINIMO) na hora anterior.
    Ex: hora_atual=18 -> verifica vendas entre 17:00 e 17:59.
    Retorna (total_valor, count_transacoes_validas).

    Estrutura da tabela:
    - Linha 17 colunas: col[1]=loja_id (ou "Total"), col[3]=data_hora, col[5]=valor_op
    - Linha 16 colunas: col[1]=cod_auth, col[2]=data_hora, col[4]=valor_op
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
    hora_ref = hora_atual - 1   # hora anterior
    inicio_min = hora_ref * 60
    fim_min    = hora_atual * 60  # exclusive: pega 17:00 ate 17:59

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

            # Filtrar hora anterior (17:00 ate 17:59)
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
                if valor <= VALOR_MINIMO:
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
        hora_str = normalizar_hora(HORA_SIMULADA) if HORA_SIMULADA else "12:00"
        agora_br = datetime.strptime(DATA_SIMULADA + " " + hora_str, "%d/%m/%Y %H:%M")
        if MIN_SIMULADA:
            agora_br = agora_br.replace(minute=int(MIN_SIMULADA.strip()))
    else:
        import pytz
        tz_br = pytz.timezone("America/Sao_Paulo")
        agora_br = datetime.now(tz_br).replace(tzinfo=None)

    hora_atual = agora_br.hour
    min_atual  = agora_br.minute
    data_str   = agora_br.strftime("%d/%m/%Y")

    # Horario comercial: 11h-22h
    if not (11 <= hora_atual <= 22):
        print(f"Fora do horario comercial ({hora_atual}h). Nada enviado.")
        return

    # As 11h e o inicio do dia: zera todos os contadores
    if hora_atual == 11:
        print(f"Inicio do dia comercial (11h). Zerando contadores.")
        contadores = {f"alerta_{loja_id}": 0 for loja_id in LOJAS}
        salvar_contadores(contadores)
        print("Contadores zerados:", contadores)
        return

    hora_ref = hora_atual - 1
    print(f"Verificando vendas > R$ {VALOR_MINIMO:.0f}: {data_str} {hora_ref:02d}:00 ate {hora_ref:02d}:59")

    if not login():
        print("ERRO: Login falhou. Abortando.")
        return

    vendas    = buscar_vendas_hora_anterior(data_str, hora_atual)
    contadores = carregar_contadores()

    for loja_id, loja_nome in LOJAS.items():
        total = vendas[loja_id]["total"]
        count = vendas[loja_id]["count"]
        print(f"{loja_nome} (loja {loja_id}): {count} vendas validas | R$ {total:.2f} entre {hora_ref:02d}:00 e {hora_ref:02d}:59")

        chave = f"alerta_{loja_id}"
        if count == 0:
            # Sem venda valida na hora anterior: incrementa e envia
            contadores[chave] = contadores.get(chave, 0) + 1
            qtd = contadores[chave]
            instrucao = INSTRUCOES[min(qtd - 1, len(INSTRUCOES) - 1)]

            assunto = f"ALERTA [{loja_nome}] Sem vendas as {hora_ref:02d}h (alerta #{qtd} hoje)"
            corpo = (
                f"ALERTA DE INATIVIDADE DE VENDAS\n"
                f"{'=' * 45}\n"
                f"Loja:             {loja_nome}\n"
                f"Hora verificada:  {hora_ref:02d}:00 - {hora_ref:02d}:59\n"
                f"Sem vendas > R$ {VALOR_MINIMO:.0f}\n"
                f"Alertas hoje:     #{qtd}\n"
                f"Horario:          {data_str} {hora_atual:02d}:00\n"
                f"{'=' * 45}\n"
                f"\nACAO NECESSARIA:\n{instrucao}\n"
                f"\nFavor verificar imediatamente!\n"
            )
            print(f"  -> ALERTA #{qtd} hoje: {loja_nome} sem vendas validas entre {hora_ref:02d}:00 e {hora_ref:02d}:59")
            enviar_email(assunto, corpo, montar_html(corpo))
        else:
            print(f"  -> {loja_nome} OK. Contador do dia permanece em {contadores.get(chave, 0)}.")

    salvar_contadores(contadores)
    print("Contadores:", contadores)

if __name__ == "__main__":
    main()
