import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuracoes
MOOMBOX_URL = "https://expositores.moombox.com.br"
USUARIO = "moombox"
SENHA = os.environ.get("MOOMBOX_PASSWORD", "")

EMAIL_REMETENTE = os.environ.get("EMAIL_USER", "") or "cap00leonardo@gmail.com"
EMAIL_DESTINATARIO = os.environ.get("EMAIL_DEST", "") or "leonardochor@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("EMAIL_PASS", "") or ""

WHATSAPP_NUMERO = os.environ.get("WHATSAPP_NUMERO", "") or os.environ.get("CALLMEBOT_USER", "") or "5521992971444"
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY", "") or os.environ.get("CALLMEBOT_KEY", "") or ""

DATA_SIMULADA = os.environ.get("DATA_SIMULADA", "")
HORA_SIMULADA = os.environ.get("HORA_SIMULADA", "")
MIN_SIMULADA = os.environ.get("MIN_SIMULADA", "")
FORCAR_MODO = os.environ.get("FORCAR_MODO", "").strip().lower()

CONTADOR_FILE = "contadores.json"
HISTORICO_FILE = "historico.json"
CONFIG_FILE = "config.json"

VALOR_MINIMO = 80.0

LOJAS = {"1": "Rio Sul", "3": "Barra Shopping", "4": "NorteShopping"}

INSTRUCOES = [
    "Verificar com o vendedor se ha algum problema no sistema de vendas.",
    "Acionar o gerente da loja para verificar o fluxo de clientes.",
    "Considerar acoes emergenciais: promocao relampago ou abordagem ativa.",
    "URGENTE: Contato direto com o responsavel da loja. Risco de fechamento sem vendas.",
]

FERIADOS = {"01/01/2026", "20/04/2026", "21/04/2026", "01/05/2026", "07/09/2026", "12/10/2026", "02/11/2026", "15/11/2026", "25/12/2026"}

def dia_sem_email(data_str, weekday):
    return data_str in FERIADOS or weekday == 6

def get_grade(data_str, weekday):
    if dia_sem_email(data_str, weekday):
        return {"oficial_inicio": 15, "oficial_fim": 21, "previa_inicio": 14, "previa_fim": 20}
    return {"oficial_inicio": 11, "oficial_fim": 22, "previa_inicio": 10, "previa_fim": 21}

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"AVISO: Nao foi possivel ler {CONFIG_FILE}: {e}")
    return {"ciclo_dias": 7, "lojas": {loja_id: {"nome": nome, "premio_inicial": 1500.0, "perda_por_alerta": 50.0, "saldo_atual": 1500.0, "ciclo_inicio": datetime.now().strftime("%d/%m/%Y")} for loja_id, nome in LOJAS.items()}}

def salvar_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"ERRO ao salvar config: {e}")

def calcular_saldo(config, loja_id, data_str):
    loja_cfg = config["lojas"].get(loja_id, {})
    ciclo_ini = loja_cfg.get("ciclo_inicio", data_str)
    ciclo_dias = config.get("ciclo_dias", 7)
    try:
        dt_hoje = datetime.strptime(data_str, "%d/%m/%Y")
        dt_ciclo = datetime.strptime(ciclo_ini, "%d/%m/%Y")
        dias_ciclo = (dt_hoje - dt_ciclo).days
    except Exception:
        dias_ciclo = 0
    if dias_ciclo >= ciclo_dias:
        premio_inicial = loja_cfg.get("premio_inicial", 1500.0)
        config["lojas"][loja_id]["saldo_atual"] = premio_inicial
        config["lojas"][loja_id]["ciclo_inicio"] = data_str
        ciclo_ini = data_str
        dias_ciclo = 0
        saldo_atual = premio_inicial
    else:
        saldo_atual = loja_cfg.get("saldo_atual", loja_cfg.get("premio_inicial", 1500.0))
    return saldo_atual, dias_ciclo, ciclo_ini

def descontar_premio(config, loja_id, data_str):
    if loja_id not in config["lojas"]:
        config["lojas"][loja_id] = {"nome": LOJAS.get(loja_id, loja_id), "premio_inicial": 1500.0, "perda_por_alerta": 50.0, "saldo_atual": 1500.0, "ciclo_inicio": data_str}
    loja_cfg = config["lojas"][loja_id]
    perda = loja_cfg.get("perda_por_alerta", 50.0)
    saldo_atual, _, _ = calcular_saldo(config, loja_id, data_str)
    novo_saldo = max(0.0, saldo_atual - perda)
    config["lojas"][loja_id]["saldo_atual"] = novo_saldo
    return novo_saldo

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
        resp = session.post(MOOMBOX_URL + "/user/login", data={"_csrf": csrf, "login-form[login]": USUARIO, "login-form[password]": SENHA, "login-form[rememberMe]": "0"}, timeout=30)
        if "logout" in resp.text.lower():
            print("Login OK")
            return True
        print("AVISO: Login pode ter falhado (sem logout na resposta)")
        return True
    except Exception as e:
        print(f"ERRO login: {e}")
        return False

def _to_float_brl(txt):
    """Converte '1.234,56' ou '1234.56' ou 'R$ 100,00' em float. Retorna None se falhar."""
    if txt is None:
        return None
    s = txt.replace("R$", "").strip()
    if not s or s == "-":
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def _extrair_hora(data_hora_txt):
    """Recebe '22/05/2026 16:21:29' e devolve (h, m) ou None."""
    if not data_hora_txt:
        return None
    partes = data_hora_txt.replace("\n", " ").split()
    if len(partes) < 2:
        return None
    hms = partes[1].split(":")
    if len(hms) < 2:
        return None
    try:
        return int(hms[0]), int(hms[1])
    except ValueError:
        return None

def buscar_vendas_janela(data_str, min_ini, min_fim):
    """
    Le /zoop/financeiro e devolve {loja_id: {'total': float, 'count': int}}
    filtrando: status succeeded, hora em [min_ini, min_fim) e valor > VALOR_MINIMO.
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

    try:
        r = session.get(MOOMBOX_URL + "/zoop/financeiro", params=params, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        current_loja = None

        for row in soup.select("table tbody tr"):
            cells = row.find_all("td")
            if not cells:
                continue

            textos = [c.get_text(" ", strip=True) for c in cells]

            # Linha de total
            if any(t.strip().lower() == "total" for t in textos):
                continue

            primeira = textos[0].strip()
            if primeira.isdigit() and primeira in LOJAS:
                current_loja = primeira
                # Layout 17 cols: [0]=Loja,[1]=CodAut,[2]=Data,[3]=VlCred,[4]=VlOper,[5]=Tipo,...,[13]=Status
                data_hora_txt = textos[2] if len(textos) > 2 else ""
                valor_op_txt = textos[4] if len(textos) > 4 else ""
                status_txt = textos[13] if len(textos) > 13 else ""
            else:
                # Layout 16 cols (sem coluna Loja, herda current_loja)
                data_hora_txt = textos[1] if len(textos) > 1 else ""
                valor_op_txt = textos[3] if len(textos) > 3 else ""
                status_txt = textos[12] if len(textos) > 12 else ""

            if current_loja not in LOJAS:
                continue

            if status_txt and status_txt.lower() not in ("", "succeeded"):
                continue

            hora = _extrair_hora(data_hora_txt)
            if hora is None:
                continue
            h, m = hora
            t_min = h * 60 + m
            if not (min_ini <= t_min < min_fim):
                continue

            valor = _to_float_brl(valor_op_txt)
            if valor is None or valor <= VALOR_MINIMO:
                continue

            resultado[current_loja]["total"] += valor
            resultado[current_loja]["count"] += 1

    except Exception as e:
        print(f"ERRO buscar Zoop {data_str}: {e}")

    return resultado

def carregar_contadores():
    if os.path.exists(CONTADOR_FILE):
        try:
            with open(CONTADOR_FILE, "r") as f:
                return json.load(f)
        except Exception:
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
        except Exception:
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

def enviar_email(assunto, corpo, html=None):
    if not GMAIL_APP_PASSWORD:
        print("AVISO: GMAIL_APP_PASSWORD nao configurado. Email nao enviado.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = EMAIL_REMETENTE
        msg["To"] = EMAIL_DESTINATARIO
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
    return "<pre style='font-family:monospace'>" + linhas + "</pre>"

def enviar_whatsapp(msg):
    if not WHATSAPP_APIKEY:
        return
    try:
        import urllib.parse
        url = "https://api.callmebot.com/whatsapp.php?phone=" + WHATSAPP_NUMERO + "&text=" + urllib.parse.quote(msg) + "&apikey=" + WHATSAPP_APIKEY
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            print(f"WhatsApp enviado para {WHATSAPP_NUMERO}")
        else:
            print(f"AVISO WhatsApp: status {r.status_code}")
    except Exception as e:
        print(f"ERRO WhatsApp (nao critico): {e}")

def normalizar_hora(h_str):
    h_str = h_str.strip()
    return h_str + ":00" if ":" not in h_str else h_str

def determinar_modo(agora_br):
    if FORCAR_MODO in ("oficial", "previa"):
        return FORCAR_MODO
    if agora_br.minute >= 30:
        return "previa"
    return "oficial"

def executar_previa(agora_br, data_str, weekday, grade):
    hora = agora_br.hour
    pi = grade["previa_inicio"]
    pf = grade["previa_fim"]
    if not (pi <= hora <= pf):
        print(f"Previa fora da janela ({pi}h-{pf}h). Hora atual: {hora}h.")
        return
    if not login():
        print("ERRO: Login falhou na previa. Abortando previa.")
        return
    min_ini = hora * 60
    min_fim = hora * 60 + 45
    print(f"PREVIA {data_str} {hora:02d}:45 -> verificando vendas entre {hora:02d}:00 e {hora:02d}:45")
    vendas = buscar_vendas_janela(data_str, min_ini, min_fim)
    for loja_id, loja_nome in LOJAS.items():
        total = vendas[loja_id]["total"]
        count = vendas[loja_id]["count"]
        print(f"  {loja_nome}: {count} vendas validas | R$ {total:.2f}")
        if count == 0:
            if dia_sem_email(data_str, weekday):
                print(f"  -> sem venda mas dia sem email ({loja_nome}). Sem aviso.")
                continue
            assunto = f"[AVISO 15 MIN] {loja_nome} - faltam 15 min para perder R$ 50"
            linhas = []
            linhas.append("AVISO PREVIO (15 min antes da rodada oficial)")
            linhas.append("=" * 45)
            linhas.append(f"Loja: {loja_nome}")
            linhas.append(f"Janela observada: {hora:02d}:00 - {hora:02d}:45")
            linhas.append("Nenhuma venda valida (acima de R$ 80) registrada.")
            linhas.append("Se nao houver venda ate o fim da hora, R$ 50 serao descontados do premio.")
            linhas.append("=" * 45)
            linhas.append("Acao: agir agora para evitar a perda.")
            corpo = chr(10).join(linhas)
            enviar_email(assunto, corpo, montar_html(corpo))

def executar_oficial(agora_br, data_str, weekday, grade):
    hora = agora_br.hour
    oi = grade["oficial_inicio"]
    of_ = grade["oficial_fim"]
    if not (oi <= hora <= of_):
        print(f"Oficial fora da janela ({oi}h-{of_}h). Hora atual: {hora}h.")
        return
    hora_ref_atual = hora - 1
    if not login():
        print("ERRO: Login falhou. Abortando oficial.")
        return
    contadores = carregar_contadores()
    config = carregar_config()
    historico = carregar_historico()
    if hora == oi:
        print(f"Primeira oficial do dia ({hora}h). Zerando contadores.")
        contadores = {f"alerta_{loja_id}": 0 for loja_id in LOJAS}
        salvar_contadores(contadores)
        if not dia_sem_email(data_str, weekday):
            linhas_saldo = []
            for loja_id, loja_nome in LOJAS.items():
                saldo, dias_ciclo, ciclo_ini = calcular_saldo(config, loja_id, data_str)
                ciclo_dias = config.get("ciclo_dias", 7)
                dias_restantes = ciclo_dias - dias_ciclo
                linha = f"{loja_nome}: R$ {saldo:.2f} (ciclo {dias_ciclo+1}/{ciclo_dias}, reinicia em {dias_restantes} dia(s))"
                linhas_saldo.append(linha)
                print(f"  {linha}")
            assunto_abertura = f"[ABERTURA] Saldo de premios - {data_str} {hora}h"
            partes = []
            partes.append(f"BOM DIA! Inicio do dia comercial ({hora}h)")
            partes.append("=" * 45)
            partes.append(f"Data: {data_str}")
            partes.append(f"Janela oficial: {oi}h - {of_}h")
            partes.append("=" * 45)
            partes.append("SALDO DE PREMIOS (acumulado do dia anterior):")
            partes.extend(linhas_saldo)
            partes.append("=" * 45)
            partes.append("Boa sorte e boas vendas!")
            corpo_abertura = chr(10).join(partes)
            enviar_email(assunto_abertura, corpo_abertura, montar_html(corpo_abertura))
            print("Mensagem de abertura enviada.")
        else:
            print("Dia sem email (dom/feriado). Mensagem de abertura suprimida.")
    ultima_data = contadores.get("ultima_data_verificada", "")
    ultima_hora = contadores.get("ultima_hora_verificada", -1)
    try:
        ultima_hora = int(ultima_hora)
    except Exception:
        ultima_hora = -1
    if ultima_data == data_str and ultima_hora >= oi - 1:
        primeira = max(ultima_hora + 1, oi - 1)
        horas_pendentes = list(range(primeira, hora_ref_atual + 1))
    else:
        horas_pendentes = [hora_ref_atual]
    if not horas_pendentes:
        horas_pendentes = [hora_ref_atual]
    horas_pendentes = [h for h in horas_pendentes if (oi - 1) <= h <= (of_ - 1)]
    print(f"Horas oficiais pendentes: {horas_pendentes} (ultima registrada: {ultima_data} {ultima_hora}h)")
    for hora_ref in horas_pendentes:
        min_ini = hora_ref * 60
        min_fim = (hora_ref + 1) * 60
        print(f"Verificando vendas > R$ {VALOR_MINIMO:.0f}: {data_str} {hora_ref:02d}:00 ate {hora_ref:02d}:59")
        vendas = buscar_vendas_janela(data_str, min_ini, min_fim)
        for loja_id, loja_nome in LOJAS.items():
            total = vendas[loja_id]["total"]
            count = vendas[loja_id]["count"]
            print(f"  {loja_nome} (loja {loja_id}): {count} vendas | R$ {total:.2f}")
            chave = f"alerta_{loja_id}"
            if count == 0:
                contadores[chave] = contadores.get(chave, 0) + 1
                qtd = contadores[chave]
                instrucao = INSTRUCOES[min(qtd - 1, len(INSTRUCOES) - 1)]
                saldo_antes, dias_ciclo, ciclo_ini = calcular_saldo(config, loja_id, data_str)
                novo_saldo = descontar_premio(config, loja_id, data_str)
                ciclo_dias = config.get("ciclo_dias", 7)
                dias_restantes = ciclo_dias - dias_ciclo
                if not dia_sem_email(data_str, weekday):
                    assunto = f"ALERTA [{loja_nome}] Sem vendas as {hora_ref:02d}h (alerta #{qtd} hoje)"
                    partes = []
                    partes.append("ALERTA DE INATIVIDADE DE VENDAS")
                    partes.append("=" * 45)
                    partes.append(f"Loja: {loja_nome}")
                    partes.append(f"Hora verificada: {hora_ref:02d}:00 - {hora_ref:02d}:59")
                    partes.append(f"Sem vendas > R$ {VALOR_MINIMO:.0f} nesse periodo")
                    partes.append(f"Alertas hoje: #{qtd}")
                    partes.append("=" * 45)
                    partes.append(f"Ciclo: {ciclo_ini} ({dias_ciclo} dia(s) de {ciclo_dias})")
                    partes.append(f"Premio atual: R$ {novo_saldo:.2f} (era R$ {saldo_antes:.2f}, -R$ {saldo_antes - novo_saldo:.2f})")
                    partes.append(f"Dias restantes no ciclo: {dias_restantes}")
                    partes.append(f"Acao recomendada: {instrucao}")
                    corpo = chr(10).join(partes)
                    enviar_email(assunto, corpo, montar_html(corpo))
                    print(f"  -> ALERTA #{qtd}: {loja_nome} | Premio: R$ {novo_saldo:.2f}")
                else:
                    print(f"  -> Desconto silencioso (dom/feriado): {loja_nome} -R$ 50 | Premio: R$ {novo_saldo:.2f}")
                registrar_alerta_historico(historico, data_str, hora_ref, loja_id)
            else:
                hora_str_ref = f"{hora_ref:02d}:00"
                if data_str in historico and loja_id in historico.get(data_str, {}):
                    if hora_str_ref in historico[data_str][loja_id]:
                        historico[data_str][loja_id].remove(hora_str_ref)
                    if not historico[data_str][loja_id]:
                        del historico[data_str][loja_id]
                    if not historico.get(data_str):
                        del historico[data_str]
                saldo_atual, _, _ = calcular_saldo(config, loja_id, data_str)
                print(f"  -> {loja_nome} OK. Premio: R$ {saldo_atual:.2f}")
        contadores["ultima_data_verificada"] = data_str
        contadores["ultima_hora_verificada"] = hora_ref_atual
        salvar_contadores(contadores)
        salvar_historico(historico)
        salvar_config(config)
    print("Contadores:", contadores)

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
    data_str = agora_br.strftime("%d/%m/%Y")
    weekday = agora_br.weekday()
    grade = get_grade(data_str, weekday)
    DIAS_SEMANA = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
    tipo_dia = "Feriado" if data_str in FERIADOS else DIAS_SEMANA[weekday]
    modo = determinar_modo(agora_br)
    print("Data: " + data_str + " (" + tipo_dia + ") | Hora: " + str(agora_br.hour).zfill(2) + ":" + str(agora_br.minute).zfill(2) + " | Modo: " + modo + " | Oficial: " + str(grade["oficial_inicio"]) + "h-" + str(grade["oficial_fim"]) + "h")
    if modo == "previa":
        executar_previa(agora_br, data_str, weekday, grade)
    else:
        executar_oficial(agora_br, data_str, weekday, grade)

if __name__ == "__main__":
    main()
