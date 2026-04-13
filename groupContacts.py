"""
Esse script 
"""

import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

GROUP_NAME = "CO Integrafut"

options = webdriver.ChromeOptions()
options.debugger_address = "127.0.0.1:9222"

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

# Só navega se não estiver no WhatsApp Web para evitar o refresh desnecessário
if "web.whatsapp.com" not in driver.current_url.lower():
    print("Navegando para o WhatsApp Web...")
    driver.get("https://web.whatsapp.com")

# ===== Search for group =====
try:
    # O HTML fornecido mostra um <input role="textbox">. 
    print(f"Pesquisando pelo grupo: {GROUP_NAME}...")
    # O seletor abaixo aceita tanto o novo formato (input) quanto o antigo (div).
    search_box_xpath = '//input[@role="textbox"] | //div[@role="textbox"]'
    search_box = wait.until(EC.element_to_be_clickable((By.XPATH, search_box_xpath)))
    
    search_box.click()
    # Limpa o campo usando atalhos de teclado, que é mais confiável no WhatsApp Web
    search_box.send_keys(Keys.CONTROL + "a")
    search_box.send_keys(Keys.BACKSPACE)
    search_box.send_keys(GROUP_NAME)
    search_box.send_keys(Keys.ENTER)
except TimeoutException:
    print("ERRO: Não foi possível encontrar a caixa de pesquisa. Verifique se o WhatsApp Web carregou corretamente.")
    driver.quit()
    exit()

# ===== Open group info =====
# Aguarda o cabeçalho da conversa carregar com o nome do grupo antes de clicar
print("Grupo selecionado. Abrindo informações do grupo...")

# Focamos no header dentro de 'main' para não clicar no header da lista de contatos
header_xpath = '//div[@id="main"]//header'
group_header = wait.until(EC.element_to_be_clickable((By.XPATH, header_xpath)))
group_header.click()

# Aguarda o painel lateral de informações do grupo abrir
wait.until(EC.presence_of_element_located((By.XPATH, '//*[@role="region"] | //section'))) 
time.sleep(2) # Tempo extra para carregar a lista de participantes

# ===== Expand list if "View all" button exists =====
print("Verificando se a lista de participantes precisa ser expandida...")
try:
    # Localiza o painel lateral primeiro para restringir a busca
    sidebar = driver.find_element(By.XPATH, '//*[@role="region"] | //section')
    
    # XPath robusto: busca um botão que tenha o ícone 'chevron', NÃO contenha "criptografia" 
    # e contenha o texto "mais" ou "Ver tudo"
    view_all_xpath = './/div[@role="button"][.//span[@data-icon="chevron"]][not(contains(., "criptografia"))][descendant::*[contains(text(), "mais") or contains(text(), "Ver tudo")]]'
    
    # Rola a sidebar para baixo para garantir que o botão seja carregado e visível
    print("Rolando painel lateral para encontrar botão de expansão...")
    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", sidebar)
    time.sleep(1.5)

    view_all_btn = sidebar.find_element(By.XPATH, view_all_xpath)
    driver.execute_script("arguments[0].click();", view_all_btn)
    print("Expandindo lista completa de participantes...")
    time.sleep(2)
except NoSuchElementException:
    print("Botão 'Ver tudo' não encontrado ou a lista já está visível.")

# ===== Scroll and collect participants =====
participants = set()
no_new_count = 0
IGNORE_NAMES = ["Você", "Admin do grupo", "Olá! Eu estou usando o WhatsApp."]

print("Coletando participantes...")

while True:
    # 1. Identifica qual container contém de fato a lista de participantes
    modals = driver.find_elements(By.XPATH, '//div[@role="dialog"]')

    try:
        active_container = driver.find_element(By.XPATH, '//*[@role="region"] | //section')
        print("  -> Coletando da barra lateral...")
    except NoSuchElementException:
        print("  -> ERRO: Container de contatos não encontrado!")
        break

    # Identifica o alvo do scroll (div com tabindex -1 dentro do container ativo)
    try:
        scroll_target = active_container.find_element(By.XPATH, './/div[@tabindex="-1"]')
    except NoSuchElementException:
        scroll_target = active_container

    # 2. Captura os elementos de nome
    # Removemos filtros de classe CSS que podem mudar e buscamos spans com dir="auto"
    # O uso do ponto inicial (.//) restringe a busca ao container ativo
    elements = active_container.find_elements(By.XPATH, './/div[@role="listitem"]//span[@dir="auto"]')
    
    prev_count = len(participants)

    for el in elements:
        name = el.text.strip()
        if name and name not in IGNORE_NAMES and not name.startswith("visto por último") and len(name) > 1:
            if name not in participants:
                print(f"      [+] Encontrado: {name}")
                participants.add(name)

    # 3. Executa o scroll no container correto
    # Usamos scrollTop para garantir que o WhatsApp carregue os próximos itens da lista virtual
    driver.execute_script("arguments[0].scrollTop += 500;", scroll_target)
    
    time.sleep(2) # Espera o WhatsApp carregar os novos elementos

    if len(participants) == prev_count:
        no_new_count += 1
        if no_new_count >= 3: # Tenta rolar 3 vezes sem novos nomes antes de parar
            break
    else:
        no_new_count = 0

# ===== Save CSV =====
df = pd.DataFrame(sorted(participants), columns=["Name"])
df.to_csv(f"data/group_contacts_{GROUP_NAME}.csv", index=False)
print("--------------------------------------")
print(f"Sucesso! {len(participants)} contatos salvos em data/group_contacts_{GROUP_NAME}.csv")
