import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Configuracoes ───────────────────────────────────────────────
MOOMBOX_URL = "https://expositores.moombox.com.br"
USUARIO     = "moombox"
SENHA       = "admin2020b"

EMAIL_REMETENTE    = os.environ.get("EMAIL_REMETENTE",    "cap00leonardo@gmail.com")
EMAIL_DESTINATARIO = os.environ.get("EMAIL_DESTINATARIO", "leonardochor@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# WhatsApp via CallMeBot (opcional - deixe em branco para desativar)
WHATSAPP_NUMERO  = os.environ.get("WHATSAPP_NUMERO",  "5521992971444")
WHATSAPP_APIKEY  = os.environ.get("WHATSAPP_APIKEY",  "")

DATA_SIMULADA = os.environ.get("DATA_SIMULADA", "")
HORA_SIMULADA = os.environ.get("HORA_SIMULADA", "")
MIN_SIMULADA  = os.environ.get("MIN_SIMULADA",  "")

CONTADOR_FILE = "contadores.json"
CONFIG_FILE   = "config.json"
VALOR_MINIMO  = 80.0

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

# ─── Feriados nacionais brasileiros 2026 ─────────────────────────
FERIADOS = {
        "01/01/2026",  # Confraternizacao Universal
    "16/02/2026",  # Carnaval (segunda)
    "17/02/2026",  # Carnaval (terca)
    "03/04/2026",  # Sexta-feira Santa
    "05/04/2026",  # Pascoa
    "21/04/2026",  # Tiradentes
    "01/05/2026",  # Dia do Trabalho
    "11/06/2026",  # Corpus Christi
    "07/09/2026",  # Independencia do Brasil
    "12/10/2026",  # Nossa Senhora Aparecida
    "02/11/2026",  # Finados
    "15/11/2026",  # Proclamacao da Republica
    "20/11/2026",  # Consciencia Negra
    "25/12/2026",  # Natal
}

# ─── Horario por tipo de dia ──────────────────────────────────────
def get_horario(data_str, weekday):
        if data_str in FERIADOS or weekday == 6:
                    return 14, 21
                return 11, 22

# ─── Config de premios ────────────────────────────────────────────
def carregar_config():
        """Le config.json com configuracoes de premio por loja."""
    if os.path.exists(CONFIG_FILE):
                try:
                                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                                                    return json.load(f)
                except Exception as e:
                                print(f"AVISO: Nao foi possivel ler {CONFIG_FILE}: {e}")
                        # Config padrao se arquivo nao existir
                        return {
                                    "ciclo_dias": 7,
                                    "lojas": {
                                                    loja_id: {
                                                                        "nome": nome,
                                                                        "premio_inicial": 500.0,
                                                                        "perda_por_alerta": 50.0,
                                                                        "saldo_atual": 500.0,
                                                                        "ciclo_inicio": datetime.now().strftime("%d/%m/%Y")
                                                    }
                                                    for loja_id, nome in LOJAS.items()
                                    }
                        }

def salvar_config(config):
        """Salva config.json atualizado (saldo_atual atualizado apos cada alerta)."""
    try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                                json.dump(config, f, indent=2, ensure_ascii=False)
except Exception as e:
        print(f"AVISO: Nao foi possivel salvar {CONFIG_FILE}: {e}")

def calcular_saldo(config, loja_id, data_str):
        """
            Calcula o saldo atual do premio para a loja.
                Se o ciclo tiver expirado, reinicia automaticamente.
                    Retorna (saldo, dias_no_ciclo, ciclo_inicio_str).
                        """
    ciclo_dias = config.get("ciclo_dias", 7)
    loja_cfg   = config["lojas"].get(loja_id, {})
    premio_ini = loja_cfg.get("premio_inicial", 500.0)
    saldo      = loja_cfg.get("saldo_atual", premio_ini)
    ciclo_ini  = loja_cfg.get("ciclo_inicio", data_str)

    try:
                dt_inicio = datetime.strptime(ciclo_ini, "%d/%m/%Y")
        dt_hoje   = datetime.strptime(data_str,  "%d/%m/%Y")
        dias_corridos = (dt_hoje - dt_inicio).days
    except:
        dias_corridos = 0

    # Ciclo expirado: reinicia
    if dias_corridos >= ciclo_dias:
                saldo     = premio_ini
        ciclo_ini = data_str
        dias_corridos = 0
        if loja_id in config["lojas"]:
                        config["lojas"][loja_id]["saldo_atual"]  = saldo
                        config["lojas"][loja_id]["ciclo_inicio"] = ciclo_ini

    return saldo, dias_corridos, ciclo_ini

def descontar_premio(config, loja_id, data_str):
        """
            Desconta perda_por_alerta do saldo_atual da loja.
                Saldo nao vai abaixo de R$ 0.
                    Retorna novo saldo.
                        """
    loja_cfg         = config["lojas"].get(loja_id, {})
    perda            = loja_cfg.get("perda_por_alerta", 50.0)
    saldo_atual, _, _ = calcular_saldo(config, loja_id, data_str)
    novo_saldo       = max(0.0, saldo_atual - perda)
    config["lojas"][loja_id]["saldo_atual"] = novo_saldo
    return novo_saldo

# ─── Sessao HTTP ──────────────────────────────────────────────────
def make_session():
        s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    return s

session = make_session()

def login():
        try:
                    r    = session.get(MOOMBOX_URL + "/user/login", timeout=30)
                    soup = BeautifulSoup(r.text, "html.parser")
                    csrf_tag = soup.find("input", {"name": "_csrf"})
                    if not csrf_tag:
                                    print("ERRO: csrf nao encontrado")
                                    return False
                                csrf = csrf_tag["value"]
        resp = session.post(MOOMBOX_URL + "/user/login", data={
                        "_csrf":                   csrf,
                        "login-form[login]":       USUARIO,
                        "login-form[password]":    SENHA,
                        "login-form[rememberMe]":  "0",
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
        data_enc  = data_str + " - " + data_str
    params    = {
                "TransacaoPosSearch[data]":               data_enc,
                "TransacaoPosSearch[status]":             "succeeded",
                "TransacaoPosSearch[authorization_code]": "",
                "TransacaoPosSearch[tipo_pagamento]":     "",
                "TransacaoPosSearch[entry_mode]":         "",
                "TransacaoPosSearch[id_zoop]":            "",
    }
    resultado = {loja_id: {"total": 0.0, "count": 0} for loja_id in LOJAS}
    hora_ref  = hora_atual - 1
    inicio_min = hora_ref * 60
    fim_min    = hora_atual * 60

    try:
                r    = session.get(MOOMBOX_URL + "/zoop/financeiro", params=params, timeout=30)
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

# ─── WhatsApp via CallMeBot ───────────────────────────────────────
def enviar_whatsapp(mensagem):
        """Envia mensagem via CallMeBot. Erros nao interrompem o fluxo."""
    if not WHATSAPP_APIKEY:
                print("WhatsApp ignorado: WHATSAPP_APIKEY nao configurado.")
        return
    try:
                url = "https://api.callmebot.com/whatsapp.php"
        params = {
                        "phone":   WHATSAPP_NUMERO,
                        "text":    mensagem,
                        "apikey":  WHATSAPP_APIKEY,
        }
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
                        print(f"WhatsApp enviado para {WHATSAPP_NUMERO}")
else:
            print(f"AVISO WhatsApp: status {r.status_code} - {r.text[:200]}")
except Exception as e:
        print(f"ERRO WhatsApp (nao critico): {e}")

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
        tz_br    = pytz.timezone("America/Sao_Paulo")
        agora_br = datetime.now(tz_br).replace(tzinfo=None)

    hora_atual = agora_br.hour
    data_str   = agora_br.strftime("%d/%m/%Y")
    weekday    = agora_br.weekday()  # 0=seg, 5=sab, 6=dom

    DIAS_SEMANA = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
    tipo_dia    = "Feriado" if data_str in FERIADOS else DIAS_SEMANA[weekday]
    hora_inicio, hora_fim = get_horario(data_str, weekday)

    print(f"Data: {data_str} ({tipo_dia}) | Horario: {hora_inicio}h-{hora_fim}h | Hora atual: {hora_atual}h")

    if not (hora_inicio <= hora_atual < hora_fim) and not (hora_atual == hora_fim and agora_br.minute != 0):
                print("Fora do horario de funcionamento. Nada enviado.")
        return

    # Primeira hora do dia: zera contadores
    if hora_atual == hora_inicio:
                print(f"Inicio do dia comercial ({hora_inicio}h). Zerando contadores.")
        contadores = {f"alerta_{loja_id}": 0 for loja_id in LOJAS}
        salvar_contadores(contadores)
        print("Contadores zerados:", contadores)
        return

    hora_ref = hora_atual - 1
    print(f"Verificando vendas > R$ {VALOR_MINIMO:.0f}: {data_str} {hora_ref:02d}:00 ate {hora_ref:02d}:59")

    if not login():
                print("ERRO: Login falhou. Abortando.")
        return

    vendas     = buscar_vendas_hora_anterior(data_str, hora_atual)
    contadores = carregar_contadores()
    config     = carregar_config()

    for loja_id, loja_nome in LOJAS.items():
                total = vendas[loja_id]["total"]
        count = vendas[loja_id]["count"]
        print(f"{loja_nome} (loja {loja_id}): {count} vendas validas | R$ {total:.2f} entre {hora_ref:02d}:00 e {hora_ref:02d}:59")

        chave = f"alerta_{loja_id}"
        if count == 0:
                        contadores[chave] = contadores.get(chave, 0) + 1
            qtd      = contadores[chave]
            instrucao = INSTRUCOES[min(qtd - 1, len(INSTRUCOES) - 1)]

            # Calcular e descontar premio
            saldo_antes, dias_ciclo, ciclo_ini = calcular_saldo(config, loja_id, data_str)
            novo_saldo = descontar_premio(config, loja_id, data_str)
            ciclo_dias = config.get("ciclo_dias", 7)
            dias_restantes = ciclo_dias - dias_ciclo

            # Montar mensagem
            linha_premio = (
                                f"Ciclo: {ciclo_ini} ({dias_ciclo} dia(s) de {ciclo_dias})\n"
                                f"Premio atual: R$ {novo_saldo:.2f}  (era R$ {saldo_antes:.2f}, -R$ {saldo_antes - novo_saldo:.2f})\n"
                                f"Dias restantes no ciclo: {dias_restantes}\n"
            )

            assunto = f"ALERTA [{loja_nome}] Sem vendas as {hora_ref:02d}h (alerta #{qtd} hoje)"
            corpo = (
                                f"ALERTA DE INATIVIDADE DE VENDAS\n"
                                f"{'=' * 45}\n"
                                f"Loja: {loja_nome}\n"
                                f"Hora verificada: {hora_ref:02d}:00 - {hora_ref:02d}:59\n"
                                f"Sem vendas > R$ {VALOR_MINIMO:.0f}\n"
                                f"Alertas hoje: #{qtd}\n"
                                f"Horario: {data_str} ({tipo_dia}) {hora_atual:02d}:00\n"
                                f"{'=' * 45}\n"
                                f"\n[PROGRAMA DE PREMIOS]\n"
                                f"{linha_premio}"
                                f"{'=' * 45}\n"
                                f"\nACAO NECESSARIA:\n{instrucao}\n"
                                f"\nFavor verificar imediatamente!\n"
            )

            # Mensagem WhatsApp (mais curta)
            msg_wpp = (
                                f"ALERTA #{qtd} - {loja_nome}\n"
                                f"Sem vendas > R${VALOR_MINIMO:.0f} das {hora_ref:02d}:00 as {hora_ref:02d}:59\n"
                                f"Premio restante: R$ {novo_saldo:.2f} (-R$ {saldo_antes - novo_saldo:.2f})\n"
                                f"Dias no ciclo: {dias_ciclo}/{ciclo_dias}\n"
                                f"Acao: {instrucao}"
            )

            print(f" -> ALERTA #{qtd} hoje: {loja_nome} | Premio: R$ {novo_saldo:.2f}")
            enviar_email(assunto, corpo, montar_html(corpo))
            enviar_whatsapp(msg_wpp)
else:
            saldo_atual, _, _ = calcular_saldo(config, loja_id, data_str)
            print(f" -> {loja_nome} OK. Contador permanece em {contadores.get(chave, 0)}. Premio: R$ {saldo_atual:.2f}")

    salvar_contadores(contadores)
    salvar_config(config)
    print("Contadores:", contadores)

if __name__ == "__main__":
        main()
