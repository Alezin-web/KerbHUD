## 0.17.4 — Track Map do iRacing

* **Track Map no iRacing sem "SEM POSIÇÃO DO CARRO":** o iRacing não publica a posição do carro, então o traçado agora é calculado por velocidade e direção. É só dar **uma volta completa**, de uma linha de largada até a próxima (o erro acumulado é corrigido pela própria volta). Os outros carros são colocados pela posição na volta.
* Se o desenho sair **espelhado** em relação ao mapa do iRacing, ligue "Espelhar o traçado" nas opções do Track Map (config do módulo).
* Mensagens novas no Track Map: "aguardando a linha de largada" e "volta descartada".

## 0.17.3 — Replay e Track Map no iRacing

* **"Só na pista" agora vale no replay:** no iRacing, o replay, a tela de resultado e o intervalo entre sessões não contam mais como pista (nem como garagem). Com "Só na pista" ou "Só na garagem" o overlay some nessas telas; só "Sempre" e o DEMO mostram.
* **Track Map grava em pistas com box na reta de largada** (como Navarra): o box agora ajuda a completar o traçado, em vez de impedir que ele ficasse pronto.
* **Aviso no Track Map** quando uma volta é descartada por não fechar, em vez de ficar parado no mesmo percentual.

## 0.17.2 — Pronto para o GitHub

* **Atualização sem configurar nada:** o KerbHUD já sabe onde buscar as versões novas (repositório oficial `Alezin-web/KerbHUD`). O campo *Repositório* em Config → Configurações → Atualização só precisa ser preenchido se você usar outro.
* **Novidades mais limpas:** a caixa "Nova versão disponível" mostra o texto só no seu idioma, sem marcação.
* **Página nova no GitHub:** README bilíngue (português primeiro) com imagens, atalhos e perguntas frequentes.

## 0.17.1 — Testes isolados

* Correção só nos testes automáticos: dois testes liam as pastas reais do SimOverlay no seu PC e falhavam. Nenhuma mudança no programa.

## 0.17.0 — Agora é KerbHUD

![KerbHUD](banner-0.17.0.png)

* **Novo nome e nova identidade:** o SimOverlay agora se chama **KerbHUD** — *kerb* é a zebra de pista, vermelha e branca. Novo **logo** (um K de cantos cortados sobre a zebra), ícone, banners e este painel com o visual do KerbHUD.
* **Guia de uso:** na **primeira abertura** (e em *Ajuda → Guia de uso*) o programa mostra como funciona a janela, o modo de edição e **todos os atalhos**, com um esquema ilustrado.
* **Suas coisas vêm junto:** as configurações e as pastas de dados (logos, bandeiras, layouts...) do SimOverlay são **copiadas** automaticamente para o KerbHUD na primeira execução, sem apagar nada. A pasta e o `.exe` agora se chamam KerbHUD.

## 0.16.0 — Visibilidade, idioma e barra de tarefas livre

* **"Só na pista" e "Só na garagem" agora valem de verdade:** o overlay só aparece quando o simulador está conectado e o piloto está de fato na pista (ou na garagem). Com o jogo fechado, nos menus ou sem carro, **só a opção "Sempre" mostra**. O **modo DEMO** aparece sempre, em qualquer regra.
* **Idioma:** Configurações → Geral → *Idioma* (Automático, Português ou English). Vale ao reiniciar. O README agora é bilíngue.
* **O overlay não cobre mais a barra de tarefas, a bandeja nem os menus:** enquanto você usa a barra de tarefas, um menu da bandeja ou o Iniciar, o overlay sai do "sempre no topo" e volta sozinho quando o foco retorna ao jogo.

## 0.15.1 — Ícone do KerbHUD

* O **ícone do KerbHUD** (o logo: um K sobre a zebra de pista) aparece na janela principal, nos diálogos e na **barra de tarefas** (antes ela mostraria o ícone do Python).
* O `.exe` também usa esse ícone.

## 0.15.0 — Atualização à vista e novidades

![Novidades](banner-0.15.0.png)

### Atualização
* **Barra de versão na tela inicial:** mostra a versão instalada e o botão **Verificar atualizações**. Quando há versão nova, a barra avisa e o botão vira **Baixar e instalar**.
* Depois de atualizar, o programa reinicia e mostra estas novidades.

### Novidades (este painel)
* Aparece na **primeira vez** que você abre a janela e **depois de cada atualização**, só com o que mudou desde a última vez que você viu.
* Para rever quando quiser: **Ajuda → Novidades**.

## 0.14.0 — Widgets, pasta dados e atualização

![Pasta de dados](pasta-dados.png)

### Interface
* **Aba Widgets:** cada módulo com liga/desliga, **Config** (opções do módulo, aplicadas na hora) e regra de visibilidade.
* Janela principal com menus; fechar a janela **minimiza para a bandeja**.

### Pastas
* `logos`, `flags`, `badges`, `layouts` e `tracks` agora ficam dentro de **`dados`**. O que você já tinha é **copiado** sozinho, sem apagar nada.

### Atualização
* **Ajuda → Verificar atualizações**: baixa do GitHub, confere o SHA-256 e instala, sem mexer na pasta `dados`.

## 0.13.0 — Janela principal

* Janela principal com abas **Módulos** e **Layouts** e rodapé de estado.
* Fechar = minimizar para a bandeja; **Sair** encerra de verdade.

## 0.12.0 — Configurações, atalhos e layouts

* Janela de **Configurações** (geral, atalhos, Le Mans Ultimate).
* Atalhos editáveis; novos: próximo/anterior layout e pular etapa do DEMO.
* Layouts: renomear, duplicar, exportar e importar.
* Arquivos para gerar o **.exe** (`Gerar-exe.bat`).
