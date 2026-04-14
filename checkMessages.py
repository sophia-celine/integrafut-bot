import re
import os
import io
import zipfile
import time
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from datetime import datetime, timedelta

# ===== CONFIGURAÇÕES =====
GROUP_NAME = "Gugu Integrafut 2026"
# Caminho para o arquivo .zip exportado do WhatsApp
CHAT_ZIP = f"data/Conversa do WhatsApp com {GROUP_NAME}.zip"
OUTPUT_REPORT = f"data/relatorio_pontuacao_{GROUP_NAME.replace(' ', '_')}.txt"
LOG_POINTS_FILE = f"data/log_pontos_{GROUP_NAME.replace(' ', '_')}.txt"

SEND_TO_WHATSAPP = False  # Flag para enviar o relatório automaticamente via WhatsApp
WHATSAPP_TARGET_GROUP = "Gugu Integrafut 2026" # Grupo onde o relatório será enviado

# Lista de contatos que podem validar itens (número. item)
VALIDATORS = ["Gil", "Chu Fut"]

# Configurações de Regex
CHALLENGE_PATTERN = re.compile(r'DESAFIO (DO GUGU GERAL|MUSICAL)', re.IGNORECASE)
POINT_PATTERN = re.compile(r'(\d+(?:[.,]\d+)?)\s+pontos?\s+(azul|amarelo)', re.IGNORECASE)
# Regex para capturar o número do item. 
# 1. (?:^|[\s\*\_\~\u200b\u200c\u200d\u2068\u2069]+) -> O item deve começar no início da linha ou após espaço/formatação.
#    Isso ignora automaticamente o '01.' em '13:01.' pois o ':' não é um separador válido.
# 2. (\d+) -> Captura o número completo (ex: 24).
# 3. \. -> Garante que haja um ponto após o número.
# 4. (?![0-9]) -> Impede que pegue a parte inteira de decimais (ex: ignora o '1' em '1.5').
# 5. [\s\u200b\u200c\u200d\u2068\u2069]* -> Aceita espaços e caracteres invisíveis após o ponto.
ITEM_PATTERN = re.compile(r'(?:^|[\s\*\_\~\u200b\u200c\u200d\u2068\u2069]+)(\d+)\.(?![0-9])[\s\u200b\u200c\u200d\u2068\u2069]*', re.MULTILINE)
# Regex para capturar o Timestamp completo, Remetente e Conteúdo
MSG_PATTERN = re.compile(r'^\[?(\d{2}/\d{2}/\d{4}[,\s]\s*\d{2}:\d{2})\]?\s*-\s*([^:]+):\s*(.*)$')

DAYS_LIMIT = 7          # Período de análise ampliado para cobrir a competição
# =========================


def parse_chat_file():
    cutoff_date = datetime.now().date() - timedelta(days=DAYS_LIMIT) 
    
    # Estrutura de dados simplificada: { "DESAFIO": { "azul": 0.0, "amarelo": 0.0 } }
    results = {}
    current_challenge = None
    last_msg_ts = "Nenhuma mensagem encontrada"
    log_entries = []
    terminal_errors = [] # Lista para acumular erros de numeração para o final

    if not os.path.exists(CHAT_ZIP):
        print(f"ERRO: Arquivo {CHAT_ZIP} não encontrado. Coloque o ZIP exportado na pasta 'data'.")
        return

    print(f"Analisando mensagens desde {cutoff_date}...")

    try:
        with zipfile.ZipFile(CHAT_ZIP, 'r') as z:
            txt_files = [f for f in z.namelist() if f.endswith('.txt')]
            if not txt_files:
                print("ERRO: Nenhum arquivo de texto (.txt) encontrado dentro do ZIP.")
                return
            
            with z.open(txt_files[0]) as f_bytes:
                with io.TextIOWrapper(f_bytes, encoding='utf-8') as file, \
                     open(LOG_POINTS_FILE, "w", encoding="utf-8") as log_file:
                    
                    current_msg_text = ""
                    current_ts = ""
                    current_sender = ""
                    current_raw_lines = []

                    def flush_message():
                        """Processa a mensagem acumulada antes de iniciar uma nova ou fechar o arquivo."""
                        nonlocal current_challenge, current_msg_text, current_ts, current_sender, current_raw_lines, last_msg_ts
                        if not current_msg_text or not current_challenge:
                            return

                        points_found = POINT_PATTERN.findall(current_msg_text)
                        
                        # Contabiliza itens apenas se o remetente estiver na lista de validadores
                        items_found = []
                        items_found_in_message_count = 0 # Contador para itens validados na mensagem atual
                        if current_sender in VALIDATORS:
                            nums_found_str = ITEM_PATTERN.findall(current_msg_text)
                            
                            challenge_data = results[current_challenge]
                            processed_nums_in_current_message = set() # Para evitar avisos duplicados na mesma mensagem

                            for num_str in nums_found_str:
                                num = int(num_str)
                                
                                # Check for repetition within the current message for warning purposes
                                if num in processed_nums_in_current_message:
                                    terminal_errors.append(f"  [!] {current_challenge}: Número repetido na mesma mensagem: {num} (por {current_sender} em {current_ts})")
                                processed_nums_in_current_message.add(num)

                                # Verifica se o número já foi usado (em qualquer mensagem anterior)
                                if num in challenge_data["seen_numbers"]: # Usando set para busca eficiente
                                    terminal_errors.append(f"  [!] {current_challenge}: Número repetido: {num} (por {current_sender} em {current_ts})")
                                
                                # Verifica se houve salto na sequência (apenas se o número atual for maior que o último visto)
                                if challenge_data["last_item_number_seen"] > 0 and num > challenge_data["last_item_number_seen"] + 1:
                                    terminal_errors.append(f"  [!] {current_challenge}: Salto na sequência: de {challenge_data['last_item_number_seen']} para {num} (por {current_sender} em {current_ts})")
                                
                                challenge_data["seen_numbers"].add(num) # Adiciona ao set de números vistos
                                if num > challenge_data["last_item_number_seen"]:
                                    challenge_data["last_item_number_seen"] = num # Atualiza o maior número visto
                                
                                challenge_data["itens"] += 1
                                items_found_in_message_count += 1

                        if points_found or items_found_in_message_count > 0:
                            last_msg_ts = current_ts
                            
                            for pts_str, team in points_found:
                                pts_val = float(pts_str.replace(',', '.'))
                                team_lower = team.lower()
                                results[current_challenge][team_lower] += pts_val
                                log_entries.append(f"[{current_ts}] {current_sender} -> {current_challenge}: {pts_val} pts {team_lower}")
                                print(f"  [+] {current_challenge}: +{pts_val} {team_lower} (por {current_sender})")
                            
                            if items_found_in_message_count > 0:
                                print(f"  [*] {current_challenge}: {items_found_in_message_count} itens validados por {current_sender}")
                            
                            # Salva todas as linhas originais da mensagem no log
                            log_file.write("\n".join(current_raw_lines) + "\n")
                        
                        # Limpa o buffer
                        current_msg_text, current_ts, current_raw_lines = "", "", []
                        current_sender = "" # Limpa o remetente também

                    for line in file:
                        clean_line = line.strip()
                        if not clean_line: continue
                        
                        match = MSG_PATTERN.match(clean_line)
                        if match:
                            flush_message() # Processa a mensagem anterior
                            timestamp_str, sender, message = match.groups()
                            
                            try:
                                msg_date = datetime.strptime(timestamp_str[:10], '%d/%m/%Y').date()
                            except ValueError:
                                current_msg_text, current_ts, current_sender, current_raw_lines = "", "", "", [] # Limpa tudo em caso de erro de data
                                continue
                            
                            if msg_date < cutoff_date:
                                current_msg_text, current_ts, current_sender, current_raw_lines = "", "", "", [] # Limpa tudo se a data for anterior ao corte
                                continue

                            challenge_match = CHALLENGE_PATTERN.search(message)
                            if challenge_match:
                                current_challenge = f"DESAFIO {challenge_match.group(1).upper()}"
                                if current_challenge not in results:
                                    results[current_challenge] = {"azul": 0.0, "amarelo": 0.0, "itens": 0, "seen_numbers": set(), "last_item_number_seen": 0}
                                # Também bufferiza esta mensagem, pois ela pode conter itens
                                current_msg_text = message
                                current_ts = timestamp_str
                                current_sender = sender.strip()
                                current_raw_lines = [clean_line]
                            elif current_challenge:
                                # Inicia novo buffer de mensagem
                                current_msg_text = message
                                current_ts = timestamp_str
                                current_sender = sender.strip()
                                current_raw_lines = [clean_line]
                        else:
                            # Se não houver match, é uma continuação da mensagem anterior
                            if current_ts:
                                current_msg_text += "\n" + clean_line
                                current_raw_lines.append(clean_line)
                    
                    # Processa a última mensagem do arquivo
                    flush_message()

    except zipfile.BadZipFile:
        print(f"ERRO: O arquivo {CHAT_ZIP} não é um arquivo ZIP válido ou está corrompido.")
        return

    save_report(results, log_entries, last_msg_ts)

    # Exibe os erros de contagem acumulados ao final dos prints
    if terminal_errors:
        print("\n=== ALERTAS DE COORDENAÇÃO (ERROS DE NUMERAÇÃO) ===")
        for err in terminal_errors:
            print(err)

def save_report(results, logs, last_ts):
    periodo = "hoje" if DAYS_LIMIT == 0 else f"últimos {DAYS_LIMIT} dias"
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(f"RELATÓRIO DE COMPETIÇÃO - GRUPO: {GROUP_NAME}\n")
        f.write(f"Período de análise: {periodo}\n")
        f.write(f"Última mensagem computada em: {last_ts}\n")
        f.write("-" * 50 + "\n\n")
        
        total_azul = 0
        total_amarelo = 0
        total_itens = 0

        for desafio, scores in results.items():
            f.write(f"\n=== {desafio} ===\n")
            f.write(f"Itens computados: {scores['itens']}\n")
            f.write(f"Pontuação Azul: {scores['azul']}\n")
            f.write(f"Pontuação Amarela: {scores['amarelo']}\n")
            
            total_azul += scores['azul']
            total_amarelo += scores['amarelo']
            total_itens += scores['itens']

        f.write("\n" + "=" * 50 + "\n")
        f.write(f"PONTUAÇÃO ATÉ AGORA:\n")
        f.write(f"EQUIPE AZUL: {total_azul}\n")
        f.write(f"EQUIPE AMARELA: {total_amarelo}\n")
        f.write(f"TOTAL DE ITENS VALIDADOS: {total_itens}\n")

    print("--------------------------------------")
    print(f"Análise concluída!")
    print(f"Relatório salvo em: {OUTPUT_REPORT}")
    print(f"Log de mensagens de pontuação salvo em: {LOG_POINTS_FILE}")

def send_whatsapp_report():
    """Envia o conteúdo do relatório gerado para o grupo especificado no WhatsApp Web."""
    if not os.path.exists(OUTPUT_REPORT):
        print("ERRO: Relatório não encontrado para envio.")
        return

    print(f"Conectando ao WhatsApp para enviar relatório para: {WHATSAPP_TARGET_GROUP}...")
    try:
        with open(OUTPUT_REPORT, "r", encoding="utf-8") as f:
            report_text = f.read()

        options = webdriver.ChromeOptions()
        options.debugger_address = "127.0.0.1:9222"
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)

        # Pesquisar o grupo no painel lateral
        search_xpath = '//div[@id="side"]//div[@role="textbox"]'
        search_box = wait.until(EC.element_to_be_clickable((By.XPATH, search_xpath)))
        search_box.click()
        search_box.send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
        search_box.send_keys(WHATSAPP_TARGET_GROUP, Keys.ENTER)
        time.sleep(2) # Aguarda a conversa carregar

        # Localizar o campo de digitação da mensagem
        msg_box_xpath = '//footer//div[@role="textbox"][@contenteditable="true"]'
        msg_box = wait.until(EC.element_to_be_clickable((By.XPATH, msg_box_xpath)))
        
        # Envia o texto simulando Shift+Enter para manter as quebras de linha no WhatsApp
        for line in report_text.split('\n'):
            msg_box.send_keys(line)
            msg_box.send_keys(Keys.SHIFT + Keys.ENTER)
        
        msg_box.send_keys(Keys.ENTER)
        print("Relatório enviado com sucesso via WhatsApp!")
    except Exception as e:
        print(f"ERRO ao enviar relatório via WhatsApp: {e}")

if __name__ == "__main__":
    parse_chat_file()
    if SEND_TO_WHATSAPP:
        send_whatsapp_report()