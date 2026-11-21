## 0.17.10 — Tamanho do cabeçalho e dos pilotos no Standings

* **Standings — Tamanho do cabeçalho** (XS, S, M, L): muda a barra do topo (tempo, incidentes, volta, pilotos e os títulos das colunas). **Tamanho dos pilotos** (XS, S, M, L): muda as linhas dos pilotos e os cabeçalhos de classe. "S" é o tamanho de sempre.

## 0.17.9 — Escala pelo quadrado vermelho e novas opções do Standings

* **Escala sem scroll:** a roda do mouse não muda mais o tamanho. No modo de edição, **arraste o quadrado vermelho** (borda ou canto) no Standings e no Inputs: o texto e a janela mudam juntos, mantendo a proporção, e o lado oposto fica parado. Arrastar não tira mais linhas nem colunas; para isso use as opções de Linhas. Ctrl + roda continua sendo a transparência.
* **Standings — Linhas:** "Linhas do topo" (padrão 3) e "Linhas em volta de mim" (padrão 7): **você digita o número que quiser** (até 40). Mostra o topo da sua classe, um corte e a janela comigo no meio. Substitui o antigo teto de linhas.
* **Standings — Outras classes:** "carros do topo" e "carros perto de mim" (padrão 1 e 1), também digitados. **0 e 0 esconde as outras categorias** (e os cabeçalhos delas).
* **Standings — Fonte:** escolha qualquer fonte instalada no Windows ("Padrão" é a atual).
* O preset Broadcast ganhou contagens próprias. A altura da janela continua sendo o limite de linhas.

## 0.17.8 — Segundos no tempo da sessão

* **Tempo da sessão com segundos:** a barra do topo do Standings e do Relative agora mostra o total também com segundos (`00:20:07 / 00:45:00`, antes `00:45m`).

## 0.17.7 — Fabricante pela equipe no Le Mans Ultimate

* **Logo da fabricante no LMU:** o nome do carro no LMU cita só a equipe ("Proton Competition 2025 #99"). Agora o KerbHUD tem uma tabela própria de equipe/número → fabricante (conferida com a lista do TinyPedal), então os Hypercars e GTs aparecem com a marca certa, inclusive equipes que usam carros diferentes por classe.
* Corrigido: equipes cujo nome cita uma marca (ex.: "AF Corse", "Alpine Elf") em carros LMP2 eram mostradas como Ferrari/Alpine; LMP2 é sempre Oreca.
* Equipe fora da tabela continua sem logo (nada é inventado); ajuste no `brand_overrides.json` — suas regras sempre vencem.

## 0.17.6 — Revisão geral

* **O overlay não congela mais por um erro de leitura:** antes, qualquer erro inesperado ao ler o simulador parava a captura em silêncio até reiniciar o programa. Agora o erro é registrado, a leitura continua e, se ele não passar, o KerbHUD reconecta sozinho.
* **Log de erros:** novo arquivo `kerbhud.log` (Ajuda → Abrir arquivo de log) para você me mandar quando algo der errado.
* **Configurações à prova de erro:** um `settings.json` corrompido ou com valor inválido não impede mais de abrir (o arquivo ruim é guardado como `settings.json.bad`) e ele é gravado de forma segura.
* **iRacing:** um texto de sessão estranho não trava mais a leitura. **Atualizador:** espera o programa fechar com mais segurança, tenta de novo se um arquivo estiver em uso, não apaga nada se a cópia falhar e aguenta respostas estranhas do GitHub.
* Limpeza de código sem uso e mais testes.

## 0.17.5 — Posição ao vivo no iRacing

* **Standings e Relative em tempo real na corrida do iRacing:** a posição oficial do iRacing só muda quando o carro cruza a linha de chegada. Agora, na **corrida**, o KerbHUD calcula a ordem pela posição de cada carro na pista (voltas completas + parte da volta), então as ultrapassagens aparecem na hora.
* Dá para voltar à posição oficial em Config → Configurações → "iRacing: posição ao vivo na corrida".
* No treino e na classificação nada muda: lá a ordem é pela melhor volta, que só muda quando alguém completa uma volta.

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
