# integrafut-bot
Bot para automatizar contagem de pontos da competição Integrafut 2026 do time de futsal da Escola Politécnica da USP

1. Exportar a conversa de Whatsapp incluindo arquivos de mídia
2. Copiar o arquivo .zip da conversa exportada para a pasta /data. Se ela não existir, crie. 
3. Rodar ```checkMessages.py```. Vai ser gerado um relatório de pontos dentro da pasta /data.
Obs: esse script considera mensagens de acordo com os nomes dos contatos salvos. 

Outra opção:
Acessar https://sophia-celine.github.io/integrafut-bot/Contador.html e inserir o arquivo zip para gerar o relatório de forma online. 

Iniciar sessão no Chrome no modo debug
No Windows:
``` 
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
``` 
No Linux:
``` 
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-debug"
``` 

