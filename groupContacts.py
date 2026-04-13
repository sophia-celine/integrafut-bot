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

GROUP_NAME = "Integrafut AZUL"
# GROUP_NAME = "Integrafut AMARELO 💛⚽"

options = webdriver.ChromeOptions()
options.debugger_address = "127.0.0.1:9222"

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

# Só navega se não estiver no WhatsApp Web para evitar o refresh desnecessário
if "web.whatsapp.com" not in driver.current_url.lower():
    driver.get("https://web.whatsapp.com")

# ===== Search for group =====
try:
    # O HTML fornecido mostra um <input role="textbox">. 
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
    print("Não foi possível encontrar a caixa de pesquisa. Verifique se o WhatsApp Web carregou corretamente.")
    driver.quit()
    exit()

# ===== Open group info =====
# Aguarda o cabeçalho da conversa carregar com o nome do grupo antes de clicar
# Focamos no header dentro de 'main' para não clicar no header da lista de contatos
header_xpath = '//div[@id="main"]//header'
group_header = wait.until(EC.element_to_be_clickable((By.XPATH, header_xpath)))
group_header.click()

# Aguarda o painel lateral de informações do grupo abrir
wait.until(EC.presence_of_element_located((By.XPATH, '//*[@role="region"] | //section'))) 
time.sleep(2) # Tempo extra para carregar a lista de participantes

# ===== Expand list if "View all" button exists =====
try:
    # Localiza o painel lateral primeiro para restringir a busca
    sidebar = driver.find_element(By.XPATH, '//*[@role="region"] | //section')
    
    # XPath robusto: busca um botão que tenha o ícone 'chevron', NÃO contenha "criptografia" 
    # e contenha o texto "mais" ou "Ver tudo"
    view_all_xpath = './/div[@role="button"][.//span[@data-icon="chevron"]][not(contains(., "criptografia"))][descendant::*[contains(text(), "mais") or contains(text(), "Ver tudo")]]'
    
    # Rola a sidebar para baixo para garantir que o botão seja carregado e visível
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
    # 1. Identifica o container ativo e o alvo do scroll
    try:
        # Se o modal (janela expandida) estiver aberto
        active_container = driver.find_element(By.XPATH, '//div[@role="dialog"]')
        # No modal, o scroll acontece no div com tabindex="-1"
        scroll_target = active_container.find_element(By.XPATH, './/div[@tabindex="-1"]')
    except NoSuchElementException:
        # Caso contrário, usa a barra lateral
        active_container = driver.find_element(By.XPATH, '//*[@role="region"] | //section')
        try:
            scroll_target = active_container.find_element(By.XPATH, './/div[@tabindex="-1"]')
        except:
            scroll_target = active_container

    # 2. Captura os elementos de nome
    # Removemos filtros de classe CSS que podem mudar e buscamos spans com dir="auto"
    # O uso do ponto inicial (.//) restringe a busca ao container ativo
    elements = active_container.find_elements(By.XPATH, './/div[@role="listitem"]//span[@dir="auto"]')
    
    prev_count = len(participants)

    for el in elements:
        name = el.text.strip()
        # Critérios de validação:
        # - Não ser vazio
        # - Não estar na lista de ignorados
        # - Ter mais de 1 caractere (evita ícones perdidos)
        if name and name not in IGNORE_NAMES and not name.startswith("visto por último") and len(name) > 1:
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

print(f"Saved {len(participants)} contacts.")
