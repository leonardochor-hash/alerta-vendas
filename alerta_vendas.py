import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Configuracoes ─────────────────────────────────────
MOOMBOX_URL = "https://expositores.moombox.com.br"
USUARIO     = "moombox"
SENHA       = "admin2020b"

EMAIL_REMETENTE    = os.environ.get("EMAIL_USER",  "cap00leonardo@gmail.com")
EMAIL_DESTINATARIO = os.environ.get("EMAIL_DEST", "leonardochor@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("EMAIL_PASS", "")

# WhatsApp via CallMeBot (opcional - deixe em branco para desativar)
WHATSAPP_NUMERO  = os.environ.get("WHATSAPP_NUMERO",  "5521992971444")
WHATSAPP_APIKEY  = os.environ.get("WHATSAPP_APIKEY",  "")

DATA_SIMULADA = os.environ.get("DATA_SIMULADA", "")
HORA_SIMULADA = os.environ.get("HORA_SIMULADA", "")
MIN_SIMULADA  = os.environ.get("MIN_SIMULADA",  "")

CONTADOR_FILE = "contadores.json"
HISTORICO_FILE = "historico.json"
CONFIG_FILE   = "config.json"

VALOR_MINIMO = 80.0

LOJAS = {
    "1": "Rio Sul",
    "3": "Barra Shopping",
    "4": "NorteShopping",
}

INSTRUCOES = [
    "Verificar com o vendedor se ha algum problema no sistema de vendas.",
    "Acionar o gerente da loja para verificar o fluxo de clientes.",
    "Considerar acoes emergenciais: promocao relampago ou abordagem ativa.",
    "URGENTE: Contato direto com o responsavel da loja. Risco de fechamento sem vendas.",
]

# ─── Feriados nacionais brasileiros 2026 ─────────────────
FERIADOS = {
    "01/01/2026",  # Ano Novo
    "20/04/2026",  # Pascoa (segunda-feira)
    "21/04/2026",  # Tiradentes
    "01/05/2026",  # Dia do Trabalho
    "07/09/2026",  # Independencia
    "12/10/2026",  # Nossa Senhora Aparecida
    "02/11/2026",  # Finados
    "15/11/2026",  # Proclamacao da Republica
    "25/12/2026",  # Natal
}

# ─── Horario por tipo de dia ──────────────────────────
def get_horario(data_str, weekday):
    if data_str in FERIADOS or weekday == 6:
        return 14, 21
    return 11, 22

# ─── Config de premios ────────────────────────────────
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
        print(f"ERRO ao salvar config: {e}")

def calcular_saldo(config, loja_id, data_str):
    """
    Retorna (saldo_atual, dias_ciclo, ciclo_inicio) para a loja.
    Reinicia automaticamente se o ciclo de config['ciclo_dias'] dias venceu.
    """
    loja_cfg  = config["lojas"].get(loja_id, {})
    ciclo_ini = loja_cfg.get("ciclo_inicio", data_str)
    ciclo_dias = config.get("ciclo_dias", 7)

    try:
        dt_hoje   = datetime.strptime(data_str,  "%d/%m/%Y")
        dt_ciclo  = datetime.strptime(ciclo_ini, "%d/%m/%Y")
        dias_ciclo = (dt_hoje - dt_ciclo).days
    except Exception:
        dias_ciclo = 0

    if dias_ciclo >= ciclo_dias:
        # Reinicia ciclo
        premio_inicial = loja_cfg.get("premio_inicial", 500.0)
        config["lojas"][loja_id]["saldo_atual"]   = premio_inicial
        config["lojas"][loja_id]["ciclo_inicio"]  = data_str
        ciclo_ini  = data_str
        dias_ciclo = 0
        saldo_atual = premio_inicial
    else:
        saldo_atual = loja_cfg.get("saldo_atual", loja_cfg.get("premio_inicial", 500.0))

    return saldo_atual, dias_ciclo, ciclo_ini

def descontar_premio(config, loja_id, data_str):
    """
    Desconta perda_por_alerta do saldo_atual da loja.
    Retorna novo saldo.
    """
    # Garante que a entrada da loja existe no config
    if loja_id not in config["lojas"]:
        config["lojas"][loja_id] = {
            "nome": LOJAS.get(loja_id, loja_id),
            "premio_inicial": 500.0,
            "perda_por_alerta": 50.0,
            "saldo_atual": 500.0,
            "ciclo_inicio": data_str
        }
    loja_cfg         = config["lojas"][loja_id]
    perda            = loja_cfg.get("perda_por_alerta", 50.0)
    saldo_atual, _, _ = calcular_saldo(config, loja_id, data_str)
    novo_saldo       = max(0.0, saldo_atual - perda)
    config["lojas"][loja_id]["saldo_atual"] = novo_saldo
    return novo_saldo

# ─── Sessao HTTP ──────────────────────────────────
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
        print("AVISO: Login pode ter falhado (sem 'logout' na resposta)")
        return True
    except Exception as e:
        print(f"ERRO login: {e}")
        return False

# ─── Busca vendas na hora anterior completa ─────────────────
def buscar_vendas_hora_anterior(data_str, hora_atual):
    """
    Verifica vendas validas (valor > VALOR_MINIMO) na hora anterior.
    Ex: hora_atual=15 -> verifica 14:00 ate 14:59.
    Usa endpoint /zoop/financeiro com TransacaoPosSearch.
    """
    data_enc   = data_str + " - " + data_str
    params = {
        "TransacaoPosSearch[data]":               data_enc,
        "TransacaoPosSearch[status]":             "succeeded",
        "TransacaoPosSearch[authorization_code]": "",
        "TransacaoPosSearch[tipo_pagamento]":     "",
        "TransacaoPosSearch[entry_mode]":         "",
        "TransacaoPosSearch[id_zoop]":            "",
    }
    resultado  = {loja_id: {"total": 0.0, "count": 0} for loja_id in LOJAS}
    hora_ref   = hora_atual - 1
    inicio_min = hora_ref   * 60
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
                h      = int(partes[0])
                m      = int(partes[1])
                t_min  = h * 60 + m
                if not (inicio_min <= t_min < fim_min):
                    continue
            except:
                continue

            try:
                valor = float(valor_op.replace(",", ".").replace("R$", "").strip())
                if valor <= VALOR_MINIMO:
                    continue
                resultado[current_loja]["total"] += valor
                resultado[current_loja]["count"] += 1
            except:
                pass

    except Exception as e:
        print(f"ERRO buscar Zoop {data_str}: {e}")

    return resultado

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

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def salvar_historico(historico):
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(historico, f, indent=2, ensure_ascii=False)

def registrar_alerta_historico(historico, data_str, hora_ref, loja_id):
    if data_str not in historico:
        historico[data_str] = {}
    if loja_id not in historico[data_str]:
        historico[data_str][loja_id] = []
    hora_str = f"{hora_ref:02d}:00"
    if hora_str not in historico[data_str][loja_id]:
        historico[data_str][loja_id].append(hora_str)

# ─── Email ────────────────────────────────────────────
def enviar_email(assunto, corpo, html=None):
    if not GMAIL_APP_PASSWORD:
        print("AVISO: GMAIL_APP_PASSWORD nao configurado. Email nao enviado.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = EMAIL_REMETENTE
        msg["To"]      = EMAIL_DESTINATARIO
        msg.attach(MIMEText(corpo, "plain", "utf-8"))
        if html:
            msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(EMAIL_REMETENTE, GMAIL_APP_PASSWORD)
            srv.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
        print(f"Email enviado: {assunto}")
    except Exception as e:
        print(f"ERRO email: {e}")

def montar_html(corpo):
    linhas = corpo.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<pre style='font-family:monospace'>{linhas}</pre>"

# ─── WhatsApp via CallMeBot ─────────────────────────────
def enviar_whatsapp(msg):
    if not WHATSAPP_APIKEY:
        return
    try:
        import urllib.parse
        url = (
            f"https://api.callmebot.com/whatsapp.php"
            f"?phone={WHATSAPP_NUMERO}"
            f"&text={urllib.parse.quote(msg)}"
            f"&apikey={WHATSAPP_APIKEY}"
        )
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            print(f"WhatsApp enviado para {WHATSAPP_NUMERO}")
        else:
            print(f"AVISO WhatsApp: status {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"ERRO WhatsApp (nao critico): {e}")

# ─── Logica principal ─────────────────────────────────
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

    # Aviso 15 minutos antes do encerramento do periodo
    modo_aviso_fim = (agora_br.minute == 45 and hora_atual == hora_fim - 1)
    if modo_aviso_fim:
        for loja_id, loja_nome in LOJAS.items():
            assunto = f"[AVISO ENCERRAMENTO] {loja_nome} - 15 min para fechar"
            corpo = (
                f"AVISO DE ENCERRAMENTO\n"
                f"A loja {loja_nome} tem 15 min ate o fim do periodo ({hora_fim}h).\n"
                f"Prepare a equipe para fechar as vendas do dia!"
            )
            enviar_email(assunto, corpo)
        print("Aviso de encerramento enviado para todas as lojas.")
        return

    # Primeira hora do dia: zera contadores
    if hora_atual == hora_inicio:
        print(f"Inicio do dia comercial ({hora_inicio}h). Zerando contadores.")
        contadores = {f"alerta_{loja_id}": 0 for loja_id in LOJAS}
        salvar_contadores(contadores)
        return

    hora_ref = hora_atual - 1
    print(f"Verificando vendas > R$ {VALOR_MINIMO:.0f}: {data_str} {hora_ref:02d}:00 ate {hora_ref:02d}:59")

    if not login():
        print("ERRO: Login falhou. Abortando.")
        return

    vendas     = buscar_vendas_hora_anterior(data_str, hora_atual)
    contadores = carregar_contadores()
    config     = carregar_config()
    historico  = carregar_historico()

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
                + ("=" * 45 + "\n")
                + f"Loja: {loja_nome}\n"
                + f"Hora verificada: {hora_ref:02d}:00 - {hora_ref:02d}:59\n"
                + f"Sem vendas > R$ {VALOR_MINIMO:.0f} nesse periodo\n"
                + f"Alertas hoje: #{qtd}\n"
                + ("=" * 45 + "\n")
                + f"{linha_premio}"
                + f"Acao recomendada: {instrucao}\n"
            )

            msg_wpp = f"ALERTA #{qtd} hoje: {loja_nome} | Premio: R$ {novo_saldo:.2f}"

            print(f" -> ALERTA #{qtd} hoje: {loja_nome} | Premio: R$ {novo_saldo:.2f}")
            enviar_email(assunto, corpo, montar_html(corpo))
            enviar_whatsapp(msg_wpp)
            registrar_alerta_historico(historico, data_str, hora_ref, loja_id)
        else:
            # Loja vendeu - limpa alerta do historico se estava marcado falsamente
            hora_str_ref = f"{hora_ref:02d}:00"
            if data_str in historico and loja_id in historico.get(data_str, {}):
                if hora_str_ref in historico[data_str][loja_id]:
                    historico[data_str][loja_id].remove(hora_str_ref)
                    if not historico[data_str][loja_id]:
                        del historico[data_str][loja_id]
                    if not historico.get(data_str):
                        del historico[data_str]
            saldo_atual, _, _ = calcular_saldo(config, loja_id, data_str)
            print(f" -> {loja_nome} OK. Contador permanece em {contadores.get(chave, 0)}. Premio: R$ {saldo_atual:.2f}")

    salvar_contadores(contadores)
    salvar_historico(historico)
    salvar_config(config)
    print("Contadores:", contadores)

if __name__ == "__main__":
    main()
