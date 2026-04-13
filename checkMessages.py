import re
import os
import io
import zipfile
import pandas as pd
from datetime import datetime, timedelta

# ===== CONFIGURAÇÕES =====
GROUP_NAME = "CO Integrafut"
# Caminho para o arquivo .zip exportado do WhatsApp
CHAT_ZIP = f"data/Conversa do WhatsApp com CO Integrafut 2026.zip"
CONTACTS_CSV = f"data/group_contacts_{GROUP_NAME}.csv"
OUTPUT_REPORT = f"data/relatorio_final_{GROUP_NAME.replace(' ', '_')}.txt"

TARGET_MESSAGE = "okk"  # Mensagem a ser contada
DAYS_LIMIT = 7          # 0 para apenas hoje, 7 para última semana
# =========================

def load_target_names(csv_path):
    print(f"Lendo contatos de {csv_path}...")
    df_contacts = pd.read_csv(CONTACTS_CSV)
    return set(df_contacts['Name'].str.lower().unique())

def parse_chat_file():
    target_names = load_target_names(CONTACTS_CSV)
    cutoff_date = datetime.now().date() - timedelta(days=DAYS_LIMIT)
    
    # Regex para o formato padrão do WhatsApp: "DD/MM/YYYY HH:MM - Nome: Mensagem"
    # ou "[HH:MM, DD/MM/YYYY] Nome: Mensagem" (depende da exportação)
    pattern = re.compile(r'^\[?(\d{2}/\d{2}/\d{4})[,\s]\s*\d{2}:\d{2}\]?\s*-\s*([^:]+):\s*(.*)$')
    
    match_count = 0
    individual_counts = {}
    log_entries = []

    if not os.path.exists(CHAT_ZIP):
        print(f"ERRO: Arquivo {CHAT_ZIP} não encontrado. Coloque o ZIP exportado na pasta 'data'.")
        return

    print(f"Analisando mensagens desde {cutoff_date}...")

    try:
        with zipfile.ZipFile(CHAT_ZIP, 'r') as z:
            # Localiza o arquivo de texto dentro do zip (geralmente _chat.txt)
            txt_files = [f for f in z.namelist() if f.endswith('.txt')]
            if not txt_files:
                print("ERRO: Nenhum arquivo de texto (.txt) encontrado dentro do ZIP.")
                return
            
            with z.open(txt_files[0]) as f_bytes:
                # Usa TextIOWrapper para ler os bytes como string utf-8
                with io.TextIOWrapper(f_bytes, encoding='utf-8') as file:
                    for line in file:
                        match = pattern.match(line.strip())
                        if match:
                            date_str, sender, message = match.groups()
                            try:
                                msg_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                            except ValueError:
                                continue

                            # Filtro de Data
                            if msg_date >= cutoff_date:
                                # Filtro de Remetente (presente no CSV)
                                if sender.lower() in target_names:
                                    # Filtro de Mensagem
                                    if TARGET_MESSAGE.lower() in message.lower():
                                        match_count += 1
                                        individual_counts[sender] = individual_counts.get(sender, 0) + 1
                                        log_entries.append(f"[{date_str}] {sender}: {message}")
                                        print(f"  [!] Encontrado: {sender} -> {message}")
    except zipfile.BadZipFile:
        print(f"ERRO: O arquivo {CHAT_ZIP} não é um arquivo ZIP válido ou está corrompido.")
        return

    save_report(match_count, individual_counts, log_entries)

def save_report(total, counts, logs):
    periodo = "hoje" if DAYS_LIMIT == 0 else f"últimos {DAYS_LIMIT} dias"
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(f"RELATÓRIO DE COMPETIÇÃO - GRUPO: {GROUP_NAME}\n")
        f.write(f"Mensagem Alvo: '{TARGET_MESSAGE}' | Período: {periodo}\n")
        f.write("-" * 50 + "\n\n")
        
        f.write("LOG DE OCORRÊNCIAS:\n")
        for entry in logs:
            f.write(entry + "\n")
            
        f.write("\n" + "-" * 50 + "\n")
        f.write(f"TOTAL GERAL: {total}\n")
        if counts:
            f.write("\nRANKING POR PARTICIPANTE:\n")
            for name, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                f.write(f" - {name}: {count}\n")

    print("--------------------------------------")
    print(f"Análise concluída! {total} mensagens encontradas.")
    print(f"Relatório salvo em: {OUTPUT_REPORT}")

if __name__ == "__main__":
    parse_chat_file()