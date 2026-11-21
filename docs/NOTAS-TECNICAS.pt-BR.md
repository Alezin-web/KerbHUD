> Notas técnicas detalhadas e histórico completo de versões (português). O guia resumido e bilíngue está em [../README.md](../README.md).
> **Nome:** até a 0.16 o programa se chamava SimOverlay (agora KerbHUD); os textos históricos abaixo foram atualizados para o nome novo, e as pastas/configurações antigas são migradas sozinhas.
> Detailed technical notes and full version history (Portuguese). The short bilingual guide is in [../README.md](../README.md).

# KerbHUD — Etapas 1 a 7: dados, janelas/layouts, módulos, configurações, atalhos e executável

Overlay de Sim Racing para **iRacing** e **Le Mans Ultimate**.

* **Etapa 1:** captura somente-leitura, modelo de dados único, modo DEMO.
* **Etapa 7 (esta):** janela de **Configurações**, atalhos editáveis, gerenciamento de layouts e `.exe` (ver "Novidades da 0.12.0").
* **Etapa 6:** **Pneus**, **Spotter**, **Radar** e **DigFlag** (ver "Novidades da 0.10.0").
* **Etapa 5:** **Track Map**, **Combustível** e **Avarias** (ver "Novidades da 0.9.0 a 0.9.8").
* **Etapa 4:** módulos **Standings** e **Relative** completos (ver abaixo).
* **Etapa 3:** módulos **Inputs** e **Telemetria** completos.
* **Etapa 2:** janelas de overlay (sem borda, transparentes, sempre no
  topo, click-through), modo de edição, layouts, atalhos globais e ícone de bandeja.

## Modo DEMO (0.7.0): roteiro com todas as novidades

O DEMO agora é um **roteiro** de etapas (tudo sintético, com selo DEMO). Por padrão roda em ciclo (`tour`):

| Etapa | O que mostra |
|---|---|
| `treino` | Standings escondido até o 1º tempo (aparece com fade-in); pilotos entram e saem (saem apagados, OUT) |
| `quali` | idem, em outra sessão |
| `corrida` | 4 classes, disputas diretas e carros uma volta à frente/atrás no Relative, pit, abandono, NRG, logos (Toyota, Ferrari, Ligier, Oreca...), bandeiras, pneus, incidentes, SOF/iRating/licença; no fim os pilotos saem um a um e por fim **todos** (lista apagada) |
| `box` | combustível (consumo medido, quanto abastecer), parada do piloto nos boxes com reparo (tempo de reparo estilo iRacing) |
| `formulas` | categorias de nome comprido com etiqueta curta: F1600, FVee, MX-5 |
| `monoclasse` | uma classe só (Ray FF1600), cabeçalho com a quantidade de pilotos |
| `poucos` | 4 pilotos: o painel se ajusta |
| `sem_nrg` | seu carro é LMP2: a coluna NRG some |
| `lmu` | avarias por região (amassados, peça solta, superaquecimento); estilo Le Mans Ultimate: sem iRating, licença, incidentes nem bandeiras; LMP3 Adess/Duqueine; ícones de Safety Rank trocando a cada 5 s |

Escolha pela bandeja (**DEMO: cenário**, com "Pular para a próxima etapa") ou na linha de comando:
`python -m kerbhud run --sim demo --demo-scenario corrida`.

## Novidades da 0.8.0

* **Visibilidade (pista / garagem / sempre):** bandeja → **Mostrar o overlay**. A regra geral vale para todos os
  módulos e cada módulo pode ter a sua (ex.: Inputs só na pista, Standings sempre). Em modo de edição tudo aparece.
  iRacing usa `IsInGarage`; no LMU vale o carro do piloto parado na vaga da garagem. **VERIFICAR no jogo**
  (`python -m kerbhud diag` mostra "Piloto na garagem"). Sem a informação, o piloto conta como "na pista".
* **NRG por categoria:** a coluna NRG aparece se alguma categoria da sessão tem energia virtual, e só as linhas
  dessas categorias mostram o valor (as outras ficam em branco). Se nenhuma categoria tem, a coluna some.
* **Ranks do LMU (DR / SR / Driver Contact Badge):** DR e SR são TEXTO (ex.: `Gold`, `S3`) e o selo de contato tem o
  próprio texto "BADGE" no rodapé do Standings. O ícone do selo aparece onde ficaria a bandeira (Standings e Relative,
  na SUA linha). O LMU **não expõe** esses dados, nem os de OUTROS pilotos: informe os seus em `settings.json`
  (`lmu.driver_rank`, `lmu.safety_rank`, `lmu.contact_badge`; o selo: `Trusted`, `Good`, `Rookie`, `Warning`,
  `Probation`, `Creator`, `Driver`, `Staff`). Sem arquivo, o app desenha o losango do selo; para usar a arte
  oficial, copie a imagem para a pasta de ícones (bandeja → **Abrir pasta de ícones de rank**) com o nome da chave em
  minúsculas (`trusted.png`).
* **Logos que faltam...** também lista os carros cuja marca não foi reconhecida (equipe e texto do veículo), para
  completarmos as regras. No LMU todo carro LMP2 é reconhecido como Oreca; `AF Corse` e `Manthey` também.
* **Adess (LMP3):** é um CARRO/construtor (AD25 e 03 Evo), agora reconhecido como marca. A logo não vem no
  download automático: copie `adess.png` para a pasta de logos de carros e use "Recarregar logos".
* **Correção:** o item "Mostrar o nome da fabricante quando não houver logo" da bandeja dava erro ao salvar.

* **Diagnóstico salvo em arquivo (0.8.2):** os `Diagnostico-LMU.bat` e `Diagnostico-iRacing.bat` agora gravam também
  `diagnostico-lmu.txt` / `diagnostico-iracing.txt` na pasta do app (envie esse arquivo). Em linha de comando: `diag --out arquivo.txt`.

* **Marcas no LMU (0.8.4), a partir do seu diagnóstico:** o nome dos carros no LMU é `Equipe #N:livery` (ex.:
  `DKR Engineering #4`) e **não cita a fabricante**, então ela não pode ser deduzida do texto. Regras: todo
  `LMP2*` = Oreca (classe de marca única); o resto você diz **uma vez** no arquivo `brand_overrides.json` (bandeja →
  *Abrir pasta de configuração*; o modelo é criado sozinho). Exemplo:
  `{"rules": [{"match": "DKR Engineering", "class": "LMP3", "brand": "adess"}]}`. **Logos que faltam...** já mostra
  as linhas prontas para copiar; depois use *Recarregar logos*. O sufixo de jogador online (`Nome#8275`) deixou de
  aparecer nos nomes.

* **Categorias com nome comprido (0.8.5):** viram uma etiqueta curta no Standings e no Relative: Formula Ford 1600
  (ou Ray) -> `F1600`, Formula Vee -> `FVee`, Formula Renault 2.0 -> `FR2.0`, Super Formula -> `SF`, MX-5 Cup ->
  `MX-5`, GR86, GT4, TCR, NASCAR etc. (tabela em `core/classes.py`, `_ABBREV`). Nome desconhecido: "Formula X 123"
  vira `F123`; qualquer outro, as 6 primeiras letras. Se alguma categoria ficar com etiqueta ruim, me diga o nome.

## Novidades da 0.15.1

* **Ícone** na janela principal, nos diálogos e na barra de tarefas (o Windows agrupa o programa pelo identificador `KerbHUD.App`, em vez de usar o ícone do Python). O `.exe` já levava o ícone.

## Novidades da 0.15.0

* **Atualização à vista:** uma faixa fixa no topo da janela principal mostra a versão instalada e o botão **Verificar
  atualizações**. Ao encontrar versão nova, a faixa avisa e o botão fica verde: **Baixar e instalar X.Y.Z**.
* **Changelog com imagens:** a janela de novidades abre sozinha na **primeira vez** e **depois de cada atualização**
  (só com o que mudou desde a última versão vista, `last_seen_version` em `settings.json`); para rever, *Ajuda → Novidades*.
  O conteúdo vem de `CHANGELOG.md` (um `## X.Y.Z — Título` por versão; vale `###`, listas, `**negrito**`, `` `código` `` e
  `![texto](arquivo.png)` com imagens da pasta `changelog/`; URLs e caminhos fora da pasta são ignorados). **A cada versão
  nova, escreva a entrada dela no `CHANGELOG.md`** (um teste falha se faltar) e, se quiser, coloque capturas de tela em
  `changelog/`. As imagens atuais são ilustrações geradas, não capturas do programa. O `.exe` leva `CHANGELOG.md` e `changelog/` junto.

## Novidades da 0.14.0

* **Pasta `dados`:** `logos`, `flags`, `badges`, `layouts` e `tracks` ficam todas dentro de `dados\` (na raiz do KerbHUD, ou
  ao lado do `KerbHUD.exe`). Só `settings.json` continua em `%APPDATA%\KerbHUD`. **Ninguém precisa baixar nada de
  novo:** na primeira execução o programa **copia** o que já existia (de `%APPDATA%\KerbHUD\...` e das pastas soltas da
  0.13.0) para `dados\`, sem apagar nem sobrescrever. A pasta `dados` nunca é alterada por atualizações e está no `.gitignore`.
* **Aba Widgets (estilo TinyPedal):** cada módulo tem liga/desliga, **Config** (janela própria com as opções do módulo: colunas
  do Standings, canais da Telemetria, alcance do Radar, reserva do Combustível etc., tudo aplicado na hora e salvo no
  layout) e a regra de quando aparece. As opções vêm de `core/module_options.py`.
* **Atualização pela interface:** *Ajuda → Verificar atualizações...* (também na bandeja e em Configurações → Atualização).
  Mostra as novidades, baixa o release do GitHub, confere o SHA-256, instala e reinicia. Ao iniciar, avisa na bandeja se houver
  versão nova (pode desligar). Só fala com `github.com` por HTTPS, recusa zips com caminhos perigosos, guarda uma cópia do
  que foi trocado em `.backup\` e **não toca na pasta `dados`**. Configure o repositório (`usuario/repositorio`) em
  Configurações → Atualização (ou `update_repo` em `settings.json`).
  * Rodando pelo código-fonte: troca os arquivos do programa e reinicia.
  * Rodando o `.exe`: baixa o zip, e um `.bat` curto troca os arquivos depois que o programa fecha e o reabre (não testado no Windows).
* **Publicar sem ninguém gerar o `.exe`:** o arquivo `.github/workflows/release.yml` faz o GitHub (Actions, `windows-latest`)
  rodar os testes, gerar o `.exe` e publicar o Release com `KerbHUD-windows.zip`, `KerbHUD-source.zip` e os `.sha256`.

### Como publicar uma versão no GitHub (passo a passo)
1. Crie um repositório **público** (Releases privados não podem ser lidos pelo atualizador).
2. Suba o projeto (o `.gitignore` já deixa `dados/`, `dist/` etc. de fora).
3. Para cada versão: aumente `__version__` em `src/kerbhud/__init__.py` (e `pyproject.toml`), faça commit, e rode
   `git tag vX.Y.Z` e `git push origin vX.Y.Z`. O workflow confere que a tag bate com a versão, roda os testes, gera o `.exe`
   e publica o Release sozinho (acompanhe na aba *Actions*).
4. Quem já tem o KerbHUD clica em *Ajuda → Verificar atualizações...* e atualiza sem abrir o GitHub.
Quem usa o `.exe` baixa **`KerbHUD-windows.zip`** do Release uma única vez; as próximas versões vêm pela interface.
O workflow e o atualizador do `.exe` **não foram testados** (sem Windows/rede aqui): se o primeiro Release falhar, envie o log.

## Novidades da 0.13.0

* **Janela principal (estilo TinyPedal):** abre ao iniciar, com barra de menus **Overlay** (edição, visível, sempre no topo,
  recarregar, sair), **Simulador** (e cenário/pular etapa do DEMO), **Config** (Configurações..., unidades), **Ferramentas**
  (baixar logos/bandeiras, logos que faltam, abrir pastas) e **Janela**, mais as abas **Módulos** (liga/desliga cada módulo e
  escolhe quando aparece: regra geral, sempre, só pista, só garagem) e **Layouts** (ativar, renomear, duplicar, exportar,
  importar, excluir). O rodapé mostra versão, layout e simulador.
* **Fechar = minimizar para a bandeja:** o X só esconde a janela e o overlay continua; clique no ícone da bandeja (ou
  *Abrir janela principal*) para voltar. **Overlay → Sair** (ou *Sair* na bandeja) encerra de verdade. Em *Janela* dá para
  escolher abrir a janela ao iniciar, fechar-para-bandeja e lembrar posição/tamanho (`show_window_at_startup`,
  `close_to_tray`, `remember_window` em `settings.json`).
* **Pastas na raiz do KerbHUD:** `logos`, `flags` (bandeiras) e `badges` (ícones de rank do LMU) agora ficam na pasta
  do projeto (ou ao lado do `KerbHUD.exe`), fáceis de achar. Na primeira execução os arquivos que já estavam em
  `%APPDATA%\KerbHUD` são **copiados** (nada é apagado nem sobrescrito). Se a pasta raiz não for gravável, usa a antiga.
  `settings.json`, layouts e traçados continuam em `%APPDATA%\KerbHUD`.

## Novidades da 0.12.0 (Etapa 7)

* **Janela de Configurações** (bandeja → *Configurações...*): abas **Geral** (simulador, regra de visibilidade, unidades,
  taxa de leitura e de tela, meu país, nome da fabricante sem logo, embreagem do iRacing), **Atalhos**, **Le Mans
  Ultimate** (meu Driver Rank, Safety Rank e selo) e **Layouts**. *OK* grava e aplica na hora; *Aplicar* faz o mesmo sem fechar.
  Tudo é validado antes de gravar (`core/settings_schema.py`): valor inválido vira uma mensagem e **nada** é gravado.
  Só a taxa de leitura (`update_hz`) espera a próxima reconexão com o jogo.
* **Atalhos editáveis:** clique no campo e pressione a combinação (modificador + tecla); *Limpar* desliga o atalho. Atalho
  repetido é recusado e atalho já usado por outro programa é avisado. Novos atalhos (padrões): **Ctrl+Alt+→ / ←** próximo/anterior
  layout, **Ctrl+Alt+N** pula a etapa do DEMO; continuam Ctrl+Alt+E (edição), Ctrl+Alt+H (esconder) e Ctrl+Alt+1 a 4 (layouts).
* **Gerenciamento de layouts:** ativar, **renomear, duplicar, exportar e importar** (janela e menu *Layouts* da bandeja).
  A importação valida o arquivo (limite de 1 MB, estrutura e valores) e **nunca sobrescreve**: nome repetido vira `Nome (2)`.
* **DEMO:** o atalho/menu *Pular para a próxima etapa* agora tem a verificação `atalho_pula_para_a_proxima_etapa`.
* **Executável (.exe):** `Gerar-exe.bat` instala o PyInstaller, gera o ícone, roda os testes e empacota em
  `dist\KerbHUD\` (`KerbHUD.exe`, sem console, e `KerbHUD-Diagnostico.exe`, com console). Arquivos em `build_exe/`.
  **Não pude testar o empacotamento** (o ambiente de desenvolvimento não tem Windows nem internet): se der erro, envie a
  saída do .bat. Configurações e layouts continuam em `%APPDATA%\KerbHUD` (ou na pasta de `KERBHUD_HOME`).

## Novidades da 0.11.9

* **DigFlag no LMU, a amarela de setor agora é só o que MUDA:** como mesmo o valor 11 de `mSectorFlag` não resolveu (o painel
  seguia amarelo), cada setor aprende o seu **valor de repouso** (o mais frequente) e só uma **mudança** dele, mantida por
  0,4 s, vira amarela. Funciona seja qual for o número que o jogo usa para "sem bandeira". O debug
  `lmu_bandeiras_brutas` mostra também o `repouso` aprendido de cada setor.

## Novidades da 0.11.8

* **DigFlag no LMU, sempre amarela:** a bandeira amarela era acesa com qualquer valor diferente de zero em `mSectorFlag`
  (ou com `mUnderYellow`), então ficava amarela o tempo todo e escondia a azul (só aparecia o pontinho azul). Depois
  só o valor 11 valia (insuficiente, ver 0.11.9); `mUnderYellow` deixou de contar. O debug mostra
  `lmu_bandeiras_brutas` (fase, setores, `mFlag`, `mUnderYellow`, `mYellowFlagState`) para conferir com a tela do jogo.

## Novidades da 0.11.7

* **Orientação do LMU confirmada com o diagnóstico dirigindo** (107 leituras, até 277 km/h, n=2616): a frente do carro é
  `-coluna_z` (concordância 1,00; `mOri` vs movimento 0 a 5°), exatamente a leitura usada desde a 0.11.3. O `coluna_x` do
  diagnóstico anterior era um falso positivo (carro parado), que a calibração mais rígida da 0.11.6 já impede. O giro do
  volante confirmou o lado esquerdo = (-fz, fx); esse passou a ser o padrão antes de haver evidência (a orientação do
  jogo não é mais usada para o lado).

## Novidades da 0.11.6

* **Diagnóstico do LMU (arquivo enviado):** a captura foi feita com o carro parado (máx. 2,6 km/h), mas mostrou
  `pose_mOri_leitura_certa=coluna_x (0.99)`, diferente do que a 0.11.3 supunha (`-coluna_z`). Como a calibração tinha
  poucas leituras e podia ter sido enganada por saltos de posição (entrar/sair da garagem), ela ficou **mais rígida**:
  só aprende **andando de verdade** (≥ 22 km/h), com **40 leituras** e 95% de concordância.
* **Lado esquerdo pelo volante:** agora o lado esquerdo do carro no mapa é descoberto pelo **giro do rumo comparado com o
  volante** (negativo = esquerda), sem depender de nenhuma suposição sobre os eixos do `mOri`.
* **Debug novo** (módulo Status / diagnóstico): `pose_candidatos` (as 3 leituras que mais concordam com o movimento) e
  `pose_giro_volante` (evidência do lado esquerdo). Para fechar a questão da orientação, grave o diagnóstico DIRIGINDO ~30 s
  (uma reta e uma curva para cada lado).

## Novidades da 0.11.5

* **Pneus redesenhado no estilo do overlay** (usando o seu exemplo só como base dos dados): cabeçalho vermelho "PNEUS" como
  o Car Damage, o **carro visto de cima** com a **volta atual** no meio e os **quatro pneus nas pontas**. Cada pneu tem
  **três faixas** (esquerda/centro/direita da banda) na cor da temperatura (azul = fria, verde = ideal, lima/amarelo/
  laranja/vermelho = quente). Ao lado de cada pneu: o **desgaste** (número da zona mais gasta + barra com uma faixa por zona
  no iRacing; barra inteira no LMU, que informa um valor só por roda), as **três temperaturas** em fichas coloridas e a
  **pressão** discreta. Roda furada/solta: pneu contornado e faixa vermelha. Tamanho padrão 330x240.

## Novidades da 0.11.4

* **Pneus no estilo do exemplo (substituído na 0.11.5):** quatro cartões (um por roda) em volta de uma coluna central em pílula com **"LAP n"** na
  vertical. Cada cartão tem três colunas (esquerda/centro/direita da banda): o número grande é o **desgaste**
  (100 = novo; a zona mais gasta fica em **salmão** quando está abaixo de 90) e o pequeno é a **temperatura**, na mesma
  cor da faixa do topo, em degradê (azul = fria, verde = ideal, lima/amarelo/laranja/vermelho = quente). A pressão
  ficou discreta, em cinza, no pé do cartão (só se o módulo tem altura; unidade em Bandeja > Pneus). O **LMU informa um
  desgaste só por roda** (repetido nas três colunas); o iRacing informa por zona. O tamanho padrão mudou (360x180).
* **Spotter animado:** a barra **entra deslizando da borda**, a moldura **pulsa** e um **brilho sobe pela barra** como um
  carro passando, enquanto houver carro ao lado; ao sumir, sai com fade.

## Novidades da 0.11.3

* **Radar/Spotter do LMU, causa do carro "torto":** eu lia a orientação do jogo (`mOri`) pelas colunas erradas. Pelo SDK do
  rFactor 2, `mOri` são as **linhas** da matriz (X/Y/Z do mundo), então os eixos do carro são as **colunas**: frente =
  -coluna 2 e esquerda = coluna 0. Isso girava a vista do radar em um ângulo que dependia da direção do carro (com o
  carro parado de lado para a pista, os carros cruzavam na diagonal e até apareciam "atrás"). Corrigido; a
  calibração pelo movimento continua conferindo a leitura (`pose_mOri_leitura_certa` deve mostrar `-coluna_z`).
  O lado esquerdo/direito vem da própria orientação do jogo.

## Novidades da 0.11.2

* **Spotter novo:** duas **barras altas** (uma em cada borda da janela) em caixa escura translúcida com preenchimento
  laranja em degradê, como no exemplo. Acende quando há carro ao lado (dois blocos se forem dois carros) e **some com
  fade** quando livre; ao editar o layout as barras ficam visíveis. A **linha fina** marca onde o carro está (mais alto
  = à frente, mais baixo = atrás; no iRacing a posição não é informada e a linha fica fixa). **Estique a janela** para
  as barras ficarem nas laterais da tela, com a sua visão no meio. O tamanho padrão mudou (520x190): num layout já
  salvo, redimensione a janela do Spotter (ou use um preset).
* **Radar com o visual de antes** (painel redondo, anéis e cruz, seu carro verde, carros na cor da classe e
  amarelo/vermelho por distância), mantendo a **meia-lua** do carro ao lado e a **faixa** do carro vindo de trás.
* **Radar, rumo do carro (LMU):** carros passando "tortos" vinham de uma frente mal estimada, principalmente com o
  carro parado. Agora, enquanto você anda, o programa **descobre qual leitura da orientação do jogo (`mOri`) bate com o
  movimento** e usa essa leitura quando você para (o `debug` mostra `pose_mOri_leitura_certa`); a direção pelo
  movimento usa uma janela mais curta (0,6 s), que acompanha melhor as curvas.

## Novidades da 0.11.1

* **Track Map fluido:** o LMU só atualiza a posição dos carros ~5 a 10 vezes por segundo; agora o mapa estima a
  velocidade de cada carro e projeta o movimento entre as atualizações (como o radar). O DEMO LMU simula esse ritmo.
* **Radar, rumo pelo movimento (LMU):** o carro "à frente" aparecia ao lado porque a orientação do jogo (`mOri`)
  estava sendo interpretada de forma incerta. Agora, com o carro andando, a frente é para onde ele se desloca; `mOri`
  só vale parado. O `debug` mostra `pose_mOri_vs_movimento_graus` (perto de 0 = `mOri` concorda): serve para conferir.
* **Radar, menos falsos alertas:** carros em **outro trecho da pista** (perto em linha reta, longe pela volta: trechos
  paralelos, fora da pista) e carros **nos boxes** (se você não está nos boxes) não aparecem mais no radar nem no
  spotter. O alcance agora é circular.
* **Radar some quando não há ninguém perto:** aparece com **fade-in** quando um carro chega a até 22 m e some com
  **fade-out** 1,5 s depois que ninguém está perto. Na edição do layout fica sempre visível. Bandeja > Radar > "Só
  aparecer quando há carro perto" desliga isso (radar sempre visível).

## Novidades da 0.11.0

* **Radar no estilo de radar de simulador** (a partir do vídeo de referência): sem fundo, só uma mira tracejada
  (dois anéis, cruz e diagonais); seu carro em vermelho-alaranjado e os outros em branco.
* **Carro ao lado:** acende uma **meia-lua** do lado dele, com a borda reta rente ao seu carro e fade para fora
  (amarela; vermelho-alaranjado se estiver quase encostando).
* **Carro vindo de trás:** uma **faixa** sai da frente do carro dele, passa por cima do seu e segue para a frente,
  com fade no fim; amarela ou vermelho-alaranjada conforme a distância, e inclinada na direção em que ele se move.

## Novidades da 0.10.5

* **DigFlag:** **todas** as bandeiras agora piscam (2 Hz). A de **chegada** pisca invertendo o xadrez branco/preto
  (em vez de apagar, para continuar legível).
* **DEMO:** a bandeira de chegada aparece nos últimos 5 s de cada etapa (antes só aparecia no fim da corrida).

## Novidades da 0.10.4

* **DigFlag, detritos:** agora é **amarela com listras vermelhas na diagonal**, como a bandeira de verdade, e não se
  confunde mais com a amarela comum.

## Novidades da 0.10.3

* **DigFlag:** a sigla `SC` ficou mais grossa (pontos maiores e maior no painel); a moldura das outras bandeiras é
  **preta** com o miolo na cor da bandeira (SC e a preta mantêm moldura clara); o painel agora **aparece e some com
  fade** (0,35 s) em vez de surgir/sumir seco.

## Novidades da 0.10.2

* **DigFlag:** só o **Safety Car** tem sigla (`SC`, em pontos brancos) e agora tem a **moldura mais grossa** (duas
  voltas de LEDs). As outras bandeiras ficam **só na cor** (miolo e moldura da cor da bandeira; xadrez para a
  chegada; preta com miolo apagado). Amarela, safety car e vermelha piscam; as outras bandeiras ativas viram
  pontinhos coloridos no canto de baixo.

## Novidades da 0.10.1

* **DigFlag em painel de LEDs** (primeira versão; veja a 0.10.2 para o ajuste de siglas e moldura).
* **Radar fluido:** o jogo atualiza a posição dos outros carros poucas vezes por segundo (por isso travava); agora o
  radar estima a velocidade de cada carro e projeta o movimento entre as atualizações, com suavização. Se ainda quiser
  mais fluidez, suba `ui_hz` no `settings.json` (padrão 30; tente 60).
* **Radar com alertas** (visual substituído na 0.11.0): carro a até 14 m fica **amarelo** e a até 6 m **vermelho**; carro vindo de TRÁS na sua faixa
  (se aproximando, ou já colado) ganha uma **linha** amarela/vermelha atrás do seu carro.
* **DEMO:** carros chegando por trás nas etapas `corrida`, `box` e `lmu` (de longe até colar e depois recuando).

## Novidades da 0.10.0 (Etapa 6)

Quatro módulos novos (todos aparecem em Bandeja > Mostrar; os presets já os trazem):

* **Pneus:** 4 blocos coloridos pela temperatura (azul = fria, verde = boa, vermelho = quente), com a pressão (kPa ou
  psi, em Bandeja > Pneus) e a barra de desgaste (100% = novo); roda furada/solta aparece em vermelho. No LMU a faixa
  "boa" é a temperatura ideal do composto que o jogo informa (±10 °C); no iRacing usa uma faixa genérica (65 a 105 °C).
* **Spotter:** aviso VISUAL de carro ao lado (sem áudio): barra vermelha à esquerda/direita, duas barras = dois
  carros. iRacing: o simulador informa (`CarLeftRight`). LMU: calculado pela posição dos carros e a orientação do seu.
* **Radar:** vista de cima centrada no seu carro (frente para cima), carros na cor da classe, contorno vermelho para
  os muito próximos (ver 0.10.2); alcance 20/30/40/60 m (Bandeja > Radar). No iRacing a distância à frente/atrás é real, mas o lado
  só se sabe pelo aviso do simulador, por isso o radar mostra "lado estimado".
* **DigFlag:** a bandeira atual em destaque (vermelha, preta, desqualificado, reparo, amarela, safety car, azul,
  detritos, branca, chegada, verde) e as demais em etiquetas pequenas. A verde some depois de 6 s; sem bandeira nada
  é desenhado.
* **A confirmar no jogo:** nomes das variáveis de pneus do iRacing (`LFtempL/M/R`, `LFwearL/M/R`, `LFpressure`; quando o
  desgaste atualiza), `SessionFlags` e `CarLeftRight`; no LMU a orientação do carro (`mOri`), as bandeiras (fase do jogo,
  selo azul, amarelas de setor) e os limiares do spotter (carro "ao lado" = até 5,5 m à frente/atrás e 1,2 a 5,5 m de
  lado). Bandeira preta/branca não são derivadas no LMU (só o iRacing as informa).
* **DEMO:** a etapa `corrida` mostra bandeiras em sequência, carros emparelhando (spotter e radar estilo iRacing) e pneus;
  a `lmu` mostra o spotter e o radar por geometria, pneus com roda furada e as bandeiras; a `box` também tem um carro ao lado.

## Novidades da 0.9.8

* **Standings (LMU):** os chips `[DR | B2] [SR | S3]` também aparecem na SUA linha (coluna de licença/iRating, que no
  LMU fica livre) e o **ícone do selo** substitui o texto no rodapé ("BADGE" + ícone; sem ícone cai no texto).

## Novidades da 0.9.7 (cores dos níveis conferidas com a tabela do LMU)

* **Chips de rank no estilo do LMU:** DR e SR aparecem como `[DR | B2]` e `[SR | S3]` (rótulo numa faixa escura, valor
  na cor do nível: B0-B3 bronze (marrom), S1-S3 prata (cinza), G1-G3 ouro (amarelo), P1-P3 platina (azul-claro); outro: cinza), desenhados pelo próprio app (arte original,
  não a do jogo). No rodapé do Standings e na sua linha do Relative.

## Novidades da 0.9.5

* **LMU:** o Safety Rank (SR) segue a mesma lógica do Driver Rank (DR): é texto. O selo de contato ganhou o campo
  `lmu.contact_badge`, o texto "BADGE" no rodapé do Standings e o ícone na coluna da bandeira (também no Relative,
  que reserva essa coluna quando há selo).

## Novidades da 0.9.4 (Relative e Standings no LMU)

* **Relative (LMU):** como o LMU não publica incidentes, a barra de cima mostra `BAT` (batidas) e `FORA` (saídas de
  pista), contadas pela telemetria do seu carro e zeradas a cada sessão. É uma contagem DERIVADA: batida = impacto acima
  de um limite (`IMPACT_MIN` em `core/incidents.py`) e saída = as 4 rodas sobre grama/terra/brita. Os limites e os
  códigos de superfície são para VALIDAR no jogo (me diga se contar de menos ou demais).
* **Standings/Relative (LMU):** os ranks voltaram a ser escritos. O **selo de contato**
  (Rookie... Staff) aparece na coluna onde ficaria a bandeira, na SUA linha (só o seu selo é conhecido; os dos outros
  pilotos o jogo não publica).

## Novidades da 0.9.3

* **Combustível:** textos ainda maiores (o nível em litros ficou como estava). **Track Map:** sem a barra de carregamento
  durante a gravação (fica só o aviso "GRAVANDO O TRAÇADO NN%").

## Novidades da 0.9.2 (ajustes de leitura)

* **Combustível:** textos bem maiores (a coluna de abastecer virou `ABAST.` para caber).
* **Track Map:** sem quadro nem cabeçalho: só o mapa sobre o jogo.
* **Car Damage:** o módulo se chama "Car Damage" e o texto sem avarias é "SEM DANOS" (DANO LEVE / DANO FORTE).

## Novidades da 0.9.1 (Etapa 5, visual revisado)

* **Car Damage:** carro de cima com rodas e lados coloridos (verde/amarelo/vermelho) e a **saúde no centro: 100% sem
  avarias, descendo conforme os danos** (LMU). No iRacing não há percentual (o simulador não publica regiões).
* **Combustível:** barra do tanque (E ... capacidade) com o nível no centro; tabela MÉD/MÁX/MÍN com USO, VOLTAS,
  ABASTECER e FIM (sobra na bandeirada sem parar; "-" se não chega); à direita as últimas voltas (USADO e DIF).
* **Track Map:** pista escura com contorno claro; bolinhas na cor da classe com a **posição na classe**, coroa no líder
  de cada classe e anel verde no seu carro. Bandeja > Track Map: rótulo = posição na classe / número do carro / nenhum.

## Novidades da 0.9.0 (Etapa 5)

* **O piloto do DEMO se chama sempre `ieieu`**, em todas as etapas.
* **Track Map:** o traçado real do circuito é gravado numa volta sua (4 s de espera até a primeira volta limpa; mostra
  "GRAVANDO O TRAÇADO NN%") e salvo por pista em `<config>/tracks/`. Carros: pontos na cor da classe com o número; você
  em círculo branco maior; carros nos boxes apagados. No LMU a posição de todos os carros é real; no iRacing só a sua
  (GPS) é usada para gravar, e os demais são colocados pela porcentagem da volta sobre o traçado. Bandeja > Track Map:
  espelhar, números, **regravar o traçado desta pista**. O DEMO nunca grava em disco.
* **Combustível:** nível, consumo médio medido nas últimas 5 voltas limpas (sem box nem reabastecimento), voltas
  restantes, quanto falta para terminar e **quanto abastecer**; verde/amarelo/vermelho. No LMU também a energia (NRG)
  dos carros que a têm. Bandeja > Combustível: reserva de 0, 0,5, 1 ou 2 voltas. Voltas até o fim vêm do número de
  voltas ou do tempo restante (estimativa).
* **Avarias:** LMU: vista de cima com 8 regiões (leve/forte), peça solta e superaquecimento. iRacing: o simulador NÃO
  publica avarias por região; mostra só tempos de reparo obrigatório/opcional e reboque.
* Presets: Corrida mostra Track Map + Combustível + Avarias; Telemetria mostra Avarias; layouts antigos ganham os
  módulos novos (ocultos) automaticamente.
* **A confirmar no jogo:** variáveis do iRacing (`FuelLevel`, `Lat/Lon`, `PitRepairLeft`...), orientação do mapa no
  LMU (use "Espelhar" se vier invertido) e a ordem das regiões de dano do LMU.

## Regra do projeto: o DEMO acompanha toda novidade

Toda atualização que mude o que aparece na tela ou nos dados precisa ser incluída no modo DEMO na MESMA versão: uma
etapa nova ou um detalhe numa existente em `providers/demo.py`, o recurso registrado em `DEMO_FEATURES` e a
verificação em `tests/test_demo_coverage.py` (o teste falha se um recurso for declarado sem ser exibido, ou se a lista
e as verificações não baterem). Etapas 5 e 6 em diante (Track Map, Fuel, Car Damage, pneus, Spotter, Radar, DigFlag)
seguem a mesma regra.

## Roteiro das etapas
| Etapa | Conteúdo | Situação |
|---|---|---|
| 1-4 | dados dos simuladores, janelas/layouts, Inputs, Telemetria, Standings, Relative | feitas |
| **5** | Track Map, Fuel Calculator, **Car Damage** | feita (0.9.0 a 0.9.8) |
| **6** | Informações dos **pneus**, Spotter, Radar e **DigFlag** (bandeiras) | feita (0.10.0 a 0.11.9) |
| **7** | configurações completas, atalhos, gerenciamento de layouts e o executável `.exe` | feita (0.12.0; `.exe` sem teste no Windows) |
| análise geral | revisão de tudo antes de finalizar (ajustes e mudanças) | próxima (opcional) |

## Requisitos
- Windows 10/11 e Python 3.10+ (testado em 3.12).
- `pip install -r requirements.txt` (PySide6) para o overlay. Os comandos de
  diagnóstico (`diag`, `snapshot`, `probe-*`) continuam sem dependências.
- iRacing: nada a configurar (entre em uma sessão).
- Le Mans Ultimate: ative **Settings > Gameplay > Enable Plugins**. Sem isso o
  jogo não publica a memória compartilhada `LMU_Data`.

## Como abrir (recomendado): duplo clique nos .bat
| Arquivo | O que faz |
|---|---|
| `Instalar-dependencias.bat` | instala o PySide6 (só na primeira vez) |
| `KerbHUD.bat` | abre o overlay (detecta iRacing/LMU sozinho) |
| `KerbHUD-DEMO.bat` | abre com dados sintéticos (sem simulador) |
| `KerbHUD-Editar.bat` | abre já em modo de edição |
| `Diagnostico-LMU.bat` / `Diagnostico-iRacing.bat` | mostram por 60 s o que é lido do jogo |
| `Baixar-logos.bat` | baixa os logotipos das marcas (internet) |
| `Logos-que-faltam.bat` | mostra quais logos de marcas estão instaladas e quais faltam |
| `Baixar-bandeiras.bat` | baixa as bandeiras dos países/regiões (internet) |

Cada .bat usa o código **da pasta onde ele está** (caminho absoluto) e imprime a versão antes de abrir. Assim não há como
abrir sem querer uma cópia antiga: um terminal já aberto numa pasta antiga, com `set PYTHONPATH=src` (que é relativo à
pasta atual), roda o código ANTIGO.

**Atualizando para um zip novo:** (1) feche o overlay (bandeja > Sair); (2) extraia o zip em uma **pasta nova** (ou
apague a antiga); (3) abra o `KerbHUD-DEMO.bat` **dessa pasta nova**; (4) confira a versão: ela aparece no terminal
(`KerbHUD 0.15.1 ...`), no módulo **Status** do overlay (`v0.15.1`, canto direito) e no ícone da bandeja. Se o número
não for o do zip, você abriu outra cópia. Suas configurações e layouts ficam em `%APPDATA%\KerbHUD` e valem para
qualquer cópia.

## Uso (linha de comando)
```bat
cd kerbhud
set PYTHONPATH=src
python -m kerbhud run --sim demo           :: overlay com dados sintéticos (selo DEMO)
python -m kerbhud run                      :: overlay, detecta iRacing/LMU sozinho
python -m kerbhud run --edit               :: já abre em modo de edição
python -m kerbhud diag --sim demo          :: sem simulador
python -m kerbhud diag --sim lmu           :: com o LMU aberto e dentro de uma sessão
python -m kerbhud diag --sim iracing       :: com o iRacing aberto e dentro de uma sessão
python -m kerbhud snapshot --sim lmu > snap_lmu.json
python -m kerbhud probe-profile            :: procura Driver/Safety Rank em arquivos do LMU
python -m kerbhud probe-rest               :: lista endpoints da REST API local do LMU
python -m unittest discover -s tests -v       :: testes (400)
python tools\ui_smoke.py                      :: renderiza PNGs dos módulos (sem abrir janelas)
```
`--sim auto` detecta qual simulador está aberto e reconecta sozinho se ele fechar.

## Tamanho do texto fixo ao redimensionar (Standings e Inputs)
Nestes dois módulos **a janela e o texto são independentes**: arrastar as bordas no modo de edição (`Ctrl+Alt+E`) muda só a
**área visível**, nunca o tamanho do texto.
* **Standings:** janela mais baixa = menos linhas; mais estreita = menos colunas (somem primeiro NRG, voltas, pneu, delta,
  marca, licença, bandeira, última volta, melhor volta, Int e Gap; pos, número e nome ficam sempre); mais larga/alta = mais
  linhas e colunas, até o que você ativou. Bandeja > Standings > **Automático (preenche a janela)** faz a altura da janela
  decidir quantas linhas aparecem (ou escolha um máximo de 10 a 26).
* **Inputs:** ao alargar, só o **gráfico** cresce (até um mínimo de ~470 de largura); pedais, marcha, velocidade e volante
  não mudam de tamanho.
* **Para mudar o tamanho do texto:** roda do mouse sobre o módulo (modo de edição) ou bandeja > Standings/Inputs >
  **Aumentar/Diminuir o texto (±10%)**. A janela acompanha na mesma proporção, então o que aparece continua igual.
* O tamanho do texto é guardado no layout (`options.scale`, como fração da largura do monitor: vale em qualquer resolução).
  Layouts antigos são migrados mantendo o texto que já tinham.
* Os demais módulos (Relative, Telemetria, Track Map, Status) continuam como antes: o conteúdo acompanha a janela.

## Módulos Standings e Relative (Etapa 4, revisados)
Seguem o estilo dos prints de referência (tabela por classe, pílulas de licença/iRating, caixas de gap).

**STANDINGS**
* **Barra superior:** inicial da sessão (R, Q, P, W, T), tempo decorrido / duração (`00:20:07 / 00:45:00`),
  incidentes `X 6/25`, `Lap 12/~25.3` (sua volta / total, ou estimado em corrida por tempo) e a
  quantidade de pilotos (capacete). Os títulos das colunas ficam na linha de baixo.
* **Grupos por classe:** cada classe tem um cabeçalho com **ícone de capacete + quantidade de pilotos da classe** + nome (texto e capacete em preto sobre cores claras como o azul do LMP2 e em branco sobre cores escuras, com a viseira "vazada" na cor da classe), e a posição é a posição NA CLASSE. Int (para o
  da frente) e Gap (para o líder) são relativos à classe. Classes que não são a sua mostram só o topo (3 carros);
  a sua mostra o topo, um corte `···` e a janela em volta de você. Se sobra espaço, as outras classes mostram mais.
* **Colunas** (todas opcionais pela bandeja): licença + iRating, **logo real** da marca do carro, posições ganhas/perdidas desde a
  largada (▲/▼), pneu, voltas completadas, Int, Gap, **Fastest** (melhor da classe em roxo), **Last**, **NRG**
  (bateria + %, só carros com energia virtual; a bateria fica afastada do texto da coluna Last).
* Você aparece em dourado; outras classes ficam mais apagadas; `PIT`, `OUT`, `GAR`, `DSQ` nas situações.
* **Rodapé:** seu perfil (licença/iRating no iRacing; Driver/Safety Rank no LMU) e a variação projetada de iRating.
* **Corrida:** Int/Gap vêm do atraso publicado pelo simulador (voltas atrás: `+1L`). **Treino/classificação:** o
  simulador não publica diferença de tempo útil, então Int/Gap é a diferença de MELHOR VOLTA dentro da classe.

**RELATIVE**
* **Topo:** `SOF` do grid (iRacing) e incidentes `X 6/25`. **Rodapé:** sessão (`RACE`), tempo `00:00:00 / 00:24m` e `Lap 12/~25.2`.
* Cada linha: posição na classe, número com faixa da classe, piloto, **licença com Safety Rating** (`4.6 [B]`),
  **pílula de iRating com a variação projetada** (`2.5k ▼14`) e a caixa de gap. Você em dourado, com `0.0`.
  No LMU, só a SUA linha mostra `DR <rank> · SR <rank>` (o jogo não publica os dados dos outros pilotos).
* **Caixa de gap:** vermelho escuro = carro uma volta à frente; azul = uma volta atrás; na mesma volta vale o estado:
  verde (favorável), vermelho (atenção), amarelo (alerta: classe mais rápida chegando em ≤ 8 s ou tráfego lento à frente).
  A seta ao lado mostra a tendência (aproximando/afastando).
* **Disputa direta:** mesma classe e volta, até 1,0 s (configurável): a linha pisca com contorno branco.

**Nomes completos e números grandes:** os nomes dos pilotos aparecem **inteiros**, sem abreviar (nada de
"J. Chadwick") e sem reticências, no Standings e no Relative. As colunas de nome são largas (cabem ~24 letras em tamanho
cheio); se um nome for ainda maior, a **fonte encolhe até caber** (mínimo 11 px). **Melhor volta e última volta** usam negrito 23 (preenchem ~80% da coluna); **voltas, Int, Gap e NRG** usam negrito 21
(colunas mais estreitas, para não ficarem coladas). Antes era 19 (e 17). A **barra superior** (inicial da sessão, tempo, incidentes, volta e quantidade de pilotos) usa negrito 21 (antes 18),
com o ícone da sessão e o capacete maiores. Os **títulos das colunas** (Tire, Laps, Int, Gap, Fastest, Last, NRG) usam negrito 17 (antes 13). Todos encolhem se uma fonte larga (fallback do
Windows) não couber, sem invadir a coluna vizinha.

**Legibilidade:** os textos do Standings e do Relative seguem o tamanho e o estilo do print de referência: nomes,
posições e números em negrito grande (nome 18, posição 20), tempos e gaps em semibold 17, linhas de 30 de altura e
colunas mais largas. Nos layouts padrão (1920x1080) o nome do piloto fica com cerca de 16 px reais no Standings e 17 px no
Relative (um teste garante o mínimo). As logos das marcas têm 30 de tamanho (antes 22) e são desenhadas mantendo a
proporção. Os layouts padrão ficaram maiores (Standings com 51% da largura da tela);
redimensione à vontade no modo de edição.

**Cabeçalho de classe também em corrida de uma classe só:** o Standings sempre mostra o cabeçalho (capacete + quantidade de
pilotos + nome da classe), com uma ou várias classes.

**Bandeiras dos países/regiões:** coluna **Bandeira** do Standings (bandeja > Standings > colunas), ao lado do nome.
* **iRacing:** o país vem sozinho do "flair" do piloto no YAML da sessão (`FlairName`, VERIFICAR com o jogo).
* **Le Mans Ultimate:** o jogo **não informa o país**. Só dá para mostrar bandeira pelo que você escrever em
  `%APPDATA%\KerbHUD\settings.json`: `"my_country": "br"` (a sua) e `"driver_flags": {"Nome do Piloto": "pt"}` (pilotos
  que você conhece). Aceita código ISO (`br`, `gb-eng`) ou nome em inglês (`Brazil`).
* **As imagens** não vêm no app. Baixe-as uma vez (bandeja > **Baixar bandeiras dos países**, `Baixar-bandeiras.bat` ou
  `python -m kerbhud fetch-flags`): ~250 PNGs do FlagCDN na pasta `dados\flags` do KerbHUD. Também dá para colocar suas
  próprias imagens lá (`br.png`...). Sem o arquivo, nada é desenhado. Não testei o download real (sem internet no meu ambiente).

**Comportamento conforme a sessão (Standings e Relative):**
* **Corrida:** o Standings lista **todos** os pilotos. Quem não está na pista (garagem, abandono, ainda fora do mundo) ou
  **saiu da sessão** continua na lista, **apagado** (40% de opacidade, marca `OUT`), em vez de sumir. Quando todos saem ao
  fim da corrida, a **última classificação continua na tela, apagada**, até uma sessão nova começar. (Isso é feito por uma
  "memória de pilotos" por sessão, identificando cada um por nome + número do carro; reinicia ao trocar de pista/tipo de
  sessão ou quando o simulador desconecta.)
* **Treino, classificação e warm-up:** o Standings **só aparece quando alguém completa uma volta**, e lista **apenas quem
  tem tempo**, do mais rápido ao mais lento, com as posições (geral e da classe) calculadas pelo tempo. O número no
  cabeçalho da classe continua sendo o de TODOS os pilotos da classe na sessão. No modo de edição (`Ctrl+Alt+E`) ele
  aparece como uma moldura "Aparece quando alguém fizer um tempo de volta", para você poder posicioná-lo.
* **Fade-in:** o Standings **aparece com um fade-in** (0,6 s) quando passa a ter conteúdo (a primeira volta em treino/
  qualificação, o início da corrida...) em vez de surgir de repente. O fade vale para o painel inteiro (fundo e linhas) e
  respeita a transparência que você escolheu. Redimensionar a janela ou entrar mais um piloto na lista **não** repete o fade.
* **Coluna NRG:** só existe quando **o seu carro** tem energia virtual. Num carro sem NRG (ex.: LMP2/LMP3 no LMU) a
  coluna some por inteiro, **mesmo que outros carros da sessão tenham** (e o painel fica mais estreito). Se a leitura falhar
  por um instante no seu carro, a coluna não pisca; ao trocar para outro carro, ela é reavaliada. Sem piloto local
  identificado (spectator), aparece se algum carro tiver NRG. Você ainda pode desligá-la à mão em bandeja > Standings > colunas.
* **Poucos pilotos:** o painel de fundo cobre só as linhas que existem e o rodapé vem logo depois delas (sem faixa vazia).
  O **Relative** também: sem linhas em branco, a altura do painel acompanha o número de carros (o tamanho do texto não muda).
* **Relative:** quem está na pista tem prioridade; os espaços que ficariam em branco são preenchidos com carros fora da
  pista ou que saíram da sessão, **apagados**, com `OUT` e `—` no lugar do tempo (o último valor conhecido não vale mais).
* iRacing: pilotos registrados que ainda não entraram no mundo aparecem apagados na corrida (`CarIdxTrackSurface = -1`,
  VERIFICAR). Spectators e pace car continuam de fora.

**Logos das fabricantes (todos os carros):** o catálogo reconhece **48 fabricantes/construtores** e cobre a relação oficial
de carros do iRacing (mais de 170) e os do Le Mans Ultimate, incluindo Ligier (LMP3), Ray (Formula 1600), Dallara, Radical,
Riley, Skip Barber, Honda (separada da Acura), Kia, Renault, Subaru, Volkswagen, Pontiac, Buick, Holden, Ram, RUF e outras.
Carros de oval/dirt sem fabricante identificável (Sprint Car, Late Model, Street Stock, Midget...) ficam **sem marca**, de
propósito. A marca sai do nome do carro; palavras curtas só valem inteiras (por isso "Crawford" não vira Ford).
* **Os arquivos de logo não vêm no app** (são marcas registradas). O download da bandeja (**Baixar logos de carros**,
  `Baixar-logos.bat` ou `python -m kerbhud fetch-logos`) usa um repositório público de logos de carros de **rua**:
  construtores de corrida (Ray, Radical, Skip Barber, Riley, Sabre, Sheane...) provavelmente **não estão lá**.
* **O que faltar, você coloca:** copie a imagem (`png`, `webp`, `jpg` ou `svg`) para a pasta de logos com o nome da marca
  (`ray.png`, `skipbarber.png`...) e use bandeja > **Recarregar logos**. Seus arquivos **nunca são sobrescritos** pelo download.
* **Saber o que falta:** bandeja > **Logos que faltam...** lista as marcas dos carros desta sessão sem arquivo, com o nome
  exato do arquivo; `python -m kerbhud logos-status` (ou `Logos-que-faltam.bat`) mostra o catálogo inteiro.
* **Sem arquivo de logo:** o Standings mostra o **nome da fabricante em texto** (até 2 linhas, sem círculo nem sigla) até você
  colocar o arquivo; a logo real sempre tem prioridade. Para não mostrar nada, desmarque bandeja > **Mostrar o nome da
  fabricante quando não houver logo** (`"logo_wordmark": false` em `settings.json`).

**Cores das classes** (dependem do simulador):
| Classe | Cor |
|---|---|
| Hypercar (LMU) | vermelho |
| GTP e DP (iRacing) | amarelo |
| LMP2 | azul claro |
| GT3 / LMGT3 (LMU) | verde |
| GT3 / GTD, IMSA (iRacing) | vermelho rosado |
| LMP3 / GTE | roxo / laranja |
Classes desconhecidas usam a cor do simulador (ou uma cor estável gerada pelo nome). Nas classes conhecidas vale a paleta
acima, mesmo no iRacing.

**Animação de ultrapassagem** (Standings e Relative; bandeja > Animações de ultrapassagem):
quando duas linhas trocam de lugar, elas **deslizam** até a nova posição (~0,45 s), o conteúdo esmaece de leve
durante o movimento, e a linha que **subiu** ganha um destaque **verde** e a que **desceu** um destaque **vermelho** que
some em ~1 s. No Relative: verde = você passou o carro; vermelho = ele passou por você. Linhas que entram na lista
aparecem com fade-in. Em mudanças bruscas (trocar de layout ou de escopo) não anima. Linhas que SAEM da lista
desaparecem na hora (sem fade-out).

**Como cada informação é obtida (e o que é estimativa)**
| Item | iRacing | LMU |
|---|---|---|
| Licença / SR por piloto, iRating | YAML de sessão (real) | **não publicado** (só a sua linha, valor manual) |
| Tempo decorrido/total | `SessionTimeTotal` − `SessionTimeRemain` (VERIFICAR) | `mCurrentET − mStartET` e restante (VERIFICAR com `diag`) |
| Incidentes `X n/limite` | `PlayerCarMyIncidentCount` e `WeekendOptions.IncidentLimit` (VERIFICAR) | **não publicado** (item some) |
| Pneu | `CarIdxTireCompound` (VERIFICAR; 0 = seco, 1 = chuva) | telemetria de todos os veículos (VERIFICAR) |
| NRG | — | `mVirtualEnergy` de todos os veículos (VERIFICAR escala) |
| Marca do carro (logo) | `CarPath`/nome do carro | nome/arquivo do veículo; se não revelar a marca, nada é desenhado |
| SOF | calculado dos iRatings da SUA classe na sessão (pode diferir do oficial) | — |
| **iRating projetado** | **ESTIMATIVA** (modelo tipo Elo, K=200, por classe, só em corrida) | — |
| Posições ganhas ▲▼ | desde a PRIMEIRA vez que o overlay viu a corrida | idem |
| Tempo do Relative | **estimativa** (fração da volta × tempo de volta) | idem |

**O que NÃO foi implementado e por quê**
* **Variação de Safety Rating (iRacing) e de Driver/Safety Rank (LMU):** não há dado nem fórmula confiável para
  projetar em tempo real. Mostramos o valor atual; um número inventado seria pior que nenhum.
* **Bandeiras de país:** exigem imagens que não posso incluir.
* **Logotipos de marcas embutidos no app:** não distribuo (são marcas registradas dos fabricantes) e meu ambiente não
  tem internet para baixá-los. O overlay desenha a **logo real** (PNG) de cada marca, que você baixa **uma vez** com o
  menu da bandeja (**Baixar logos de carros**) ou `python -m kerbhud fetch-logos`. Eles vêm do repositório público
  `car-logos-dataset` (GitHub) e ficam na pasta `dados\logos` do KerbHUD. Sem o arquivo, **nada** é desenhado no lugar
  (sem círculo com sigla). Se uma marca não existir no repositório (comum em protótipos como Oreca ou Ligier), coloque o
  PNG você mesmo com o nome da marca (`oreca.png`, `ligier.png`...). **Não testei o download real**: validei a lógica
  com um servidor simulado; se algo falhar, a mensagem da bandeja/terminal diz o motivo e o app segue funcionando.
* Bandeira da ordem de largada correta se o overlay for aberto antes da corrida; no meio dela a referência é a abertura.

Bandeja > **Standings:** escopo, quantidade de linhas (10 a 26), rodapé de perfil e colunas. **Relative:** carros à
frente/atrás (1 a 5), limiar de disputa e iRating. Os ajustes ficam salvos no layout.

## Módulos Inputs e Telemetria (Etapa 3)
**INPUTS** (faixa compacta retangular de cantos levemente arredondados, com gráfico embutido): da esquerda
para a direita, traço do histórico (acelerador, freio e embreagem), barras verticais
dos pedais com a **porcentagem embaixo de cada uma**, marcha (N em amarelo, R em vermelho), velocidade e RPM, e o
volante, que gira com o ângulo real e mostra "L 135°"/"R 135°". Os LEDs de shift
light ocupam a **borda superior de ponta a ponta**, recortados pelo contorno do módulo. Sem dados do jogo o painel esmaece e
mostra "SEM DADOS" (nunca valores inventados).
Bandeja > **Inputs**: mostrar embreagem, mostrar direção no gráfico, janela do gráfico
(3, 6, 10 ou 20 s).

**TELEMETRIA:** gráficos em faixas empilhadas (pedais; velocidade; RPM; direção) com
cores distintas e valor atual ao lado. Cada canal liga/desliga e o histórico é
configurável (5, 10, 20, 30 ou 60 s). Picos rápidos de freio são preservados mesmo
com 60 s de histórico. Se o jogo pausa, o gráfico congela em vez de deslizar.

Configuração (bandeja do ícone): **Telemetria > canais e histórico**, **Unidades > km/h | mph**.
As escolhas de canais/histórico ficam salvas **no layout**; a unidade fica em `settings.json`.
Opções avançadas por layout (edite o `.json` do layout, campo `options` do módulo):
`inputs`: `show_clutch` (true/false), `trace_steering` (true/false), `trace_s`, `shift_start` (padrão 0.85);
`telemetry`: `history_s`, `channels`.

**Shift lights:** o iRacing pode fornecer o indicador (`ShiftIndicatorPct`); quando
não fornece, é calculado pelos limites do carro no YAML de sessão. O **LMU não
fornece** nenhum indicador: os LEDs são **derivados de RPM / RPM máximo** e só começam
a acender a partir de 85 % do RPM máximo (`shift_start`). É uma aproximação, não o
ponto de troca ideal de cada carro.

## Modo de edição e layouts (Etapa 2)
| Ação | Como |
|---|---|
| Ligar/desligar modo de edição | `Ctrl+Alt+E` ou bandeja > Modo de edição |
| Mostrar/ocultar todo o overlay | `Ctrl+Alt+H` |
| Trocar de layout | `Ctrl+Alt+1..4` (Corrida, Treino, Telemetria, Broadcast) ou bandeja > Layouts |
| Mover módulo | arrastar (modo de edição) |
| Redimensionar | arrastar bordas/cantos, ou **roda do mouse** (mantém proporção) |
| Transparência do módulo | `Ctrl` + roda do mouse |
| Desligar o encaixe na grade (8 px) | segurar `Alt` ao arrastar |
| Ocultar/mostrar um módulo | bandeja > Módulos |
| Salvar / excluir layout | bandeja > Layouts > Salvar como novo / Excluir |
| Restaurar posições originais | bandeja > Layouts > Restaurar layouts padrão (só os 4 padrão) |
| Sempre no topo, trocar simulador | bandeja |

Fora do modo de edição as janelas são **transparentes a cliques** (o mouse vai para
o simulador) e **nunca roubam o foco** (`WS_EX_NOACTIVATE`), então não interferem
na pilotagem. Alterações de posição/tamanho são salvas automaticamente.

Dados do usuário: `%APPDATA%\KerbHUD\` (`settings.json`, `state.json`,
`layouts\*.json`). Defina `KERBHUD_HOME` para uma pasta portátil. Os atalhos
podem ser trocados em `settings.json` > `hotkeys` (ex.: `"toggle_edit": "Ctrl+Shift+E"`).
Posições são salvas como fração da tela + nome do monitor: o layout sobrevive a
mudança de resolução e cai no monitor principal se o monitor sumir.

**Importante:** o overlay só aparece sobre o jogo em **janela sem borda
(Borderless/Windowed)**. Em tela cheia exclusiva o Windows não deixa outras janelas
aparecerem por cima (limitação do sistema, não do app).

**Fundo do módulo:** o painel de fundo acompanha a área do desenho. Se você redimensionar a
janela para uma proporção diferente, sobra margem transparente (a janela inteira não vira um
painel gordo).

**Atualizando de uma versão anterior:** os layouts salvos em `%APPDATA%\\KerbHUD\\layouts` são **migrados
automaticamente, uma única vez** (campo `version` 1 -> 2): o Standings e o Relative ganham o tamanho legível
(51% e 32% da largura da tela), mantendo a posição do canto superior esquerdo. Tamanhos maiores que esses (escolhidos
por você) são mantidos, e o Relative é empurrado para baixo só se o Standings ampliado passar a cobri-lo. Depois da
migração o tamanho é sempre o que você definir no modo de edição. Os demais módulos não são alterados.
(Por que isso existe: o tamanho do texto na tela = fonte x [largura da janela / largura do desenho]. Quando o desenho
fica mais largo e a janela salva continua do mesmo tamanho, o texto quase não cresce.)

**Qual versão está rodando?** `python -m kerbhud --version` mostra a versão, a pasta do código, o Python e o PySide6;
ao abrir o overlay o terminal imprime a versão, o módulo **Status** mostra `v0.15.1` no canto direito (basta uma
captura de tela) e o ícone da bandeja mostra a versão ao passar o mouse e no menu. Cada zip deve ser
extraído em uma pasta nova, e é preciso rodar o comando de dentro dela.

## Validação com o jogo aberto (importante)
Os testes automáticos usam memória simulada. Eles provam que o código lê o layout
que ele mesmo descreve, **não** que o jogo publica exatamente isso. Por favor rode
`diag` com cada simulador, em pista, e confira:

| Item | O que conferir |
|---|---|
| LMU: velocidade, marcha, RPM, pedais | batem com o HUD do jogo |
| LMU: ângulo do volante | assunção: `mPhysicalSteeringWheelRange` em graus (curso total) |
| LMU: nº do carro | extraído de `mVehicleName` (`#NN`); pode vir vazio |
| iRacing: embreagem | assunção: `ClutchRaw` = 1.0 com pedal solto. Se invertido: `"invert_clutch": false` em `config/settings.json` |
| iRacing: sentido do volante | assunção: ângulo positivo do SDK = esquerda |
| iRacing: licença / iRating | vêm do YAML de sessão (`DriverInfo.Drivers`) |
| Standings/Relative: números e classes | confira nº do carro, classe e gaps contra o HUD do jogo |
| Telemetria: aparência e fluidez | rode `run --sim demo` e depois com o jogo; informe se travar |

Envie a saída de `diag` e `snapshot` se algo divergir.

## Limitações conhecidas (sem inventar valores)
- **Etapa 2 não foi executada com Qt neste ambiente de desenvolvimento.** A lógica
  (layouts, geometria, snap, atalhos, persistência, fluxo de janelas) é testada, mas
  a aparência e o comportamento real no Windows (click-through, topo, atalhos
  globais) precisam de validação sua: rode `run --sim demo` e `tools\ui_smoke.py`.
- **LMU — Driver Rank / Safety Rank:** não encontrei confirmação de que a memória
  compartilhada ou a REST API os exponham. Por ora o valor é **manual**
  (`config/settings.json`, marcado como "manual" no modelo). `probe-profile` e
  `probe-rest` investigam fontes locais na sua máquina.
- **LMU — modelo do carro:** não há campo confirmado na memória compartilhada
  (`car_model = None`): a coluna "Modelo do carro" do Standings fica vazia no LMU (no iRacing
  funciona). Provável fonte: REST API (a investigar com `probe-rest`).
- **Classes do LMU:** só confirmei `LMP2_ELMS`, `LMP3` e `GT3` (de uma sessão real). Outros nomes
  (ex.: Hypercar) são tratados por regra de substring e podem precisar de ajuste.
- **Driver Rank / Safety Rank (LMU):** no Standings aparecem como "n/d" até você informar
  manualmente (valor marcado com `*`) ou eu achar uma fonte local.
- **LMU — leitura sem trava:** a memória é lida sem lock de sincronização do jogo;
  em raros ciclos um quadro pode vir inconsistente. Mitigação futura: dupla leitura.
- **iRacing — coordenadas:** o SDK não fornece X/Y dos carros, só `LapDistPct`; o traçado é gravado a partir do
  GPS do seu carro (Lat/Lon) numa volta e os outros carros seguem a porcentagem da volta sobre ele.
- **iRacing — abandono:** "OUT" é inferido de `TrackSurface = NotInWorld`; pode
  confundir desconexão com abandono.
- **iRacing — treino/classificação:** se `CarIdxPosition` vier zerado, a posição é
  derivada das melhores voltas (dado real, mas derivado).
- **Shift lights:** o iRacing pode fornecer `ShiftIndicatorPct`; o LMU não, então
  é derivado de RPM/RPM máx. e marcado como `derived`.

## Segurança
- Leitura apenas. Nenhum arquivo do jogo é modificado, nada é injetado, nenhum
  comando é enviado ao carro.
- No Windows abrimos a memória com `OpenFileMapping` + `FILE_MAP_READ`, que **nunca
  cria** o mapeamento. (`mmap` do Python com `tagname` usa `CreateFileMapping`, que
  cria o objeto se ele não existir; isso poderia interferir no jogo.)
- `probe-profile` só lê arquivos de texto da pasta do LMU; `probe-rest` só faz GET.

## Estrutura
```
src/kerbhud/
  core/model.py        Snapshot padronizado (campos None = indisponível)
  core/memory.py       acesso somente-leitura à memória compartilhada
  core/engine.py       detecção do simulador, polling em thread, reconexão, troca de sim
  core/layout.py       layouts, presets, geometria, snap, persistência (sem Qt)
  core/winapi.py       click-through, topo, no-activate e atalhos globais (Win32)
  ui/module_base.py    janela base: transparente, edição, arrastar/redimensionar
  core/history.py      histórico de inputs (buffer circular) + decimação preservando picos
  core/viewmodel.py    lógica de exibição de Inputs/Telemetria (sem Qt)
  ui/inputs_module.py  módulo Inputs (retângulo com gráfico embutido)
  ui/plotting.py       desenho de séries temporais compartilhado
  ui/telemetry_module.py  módulo Telemetria
  core/classes.py      nomes/cores de classe de carro, licença
  core/standings.py    classificação: gaps, escopos, colunas, seleção de linhas
  core/relative.py     proximidade, tempo estimado, tendência, cores, disputa
  core/irating.py      SOF e projeção de iRating (estimativa)
  core/sessioninfo.py  barra de sessão (relógio, incidentes, voltas, SOF)
  core/brands.py, core/tires.py, core/gridtracker.py, core/textfmt.py
  core/animation.py    animação de ultrapassagem (deslizar, esmaecer, destaque verde/vermelho)
  core/logos.py        download dos logotipos das marcas (por ação do usuário)
  ui/icons.py          ícones desenhados em código (X, capacete, bateria, pneu, selos de marca)
  ui/standings_module.py, ui/relative_module.py  módulos Standings e Relative
  ui/modules.py        Status (real) + moldura provisória do Track Map
  ui/overlay_manager.py  janelas, layout ativo, modo de edição, despacho de dados
  ui/app.py            bandeja, atalhos, ciclo de vida
  providers/lmu.py + lmu_layout.py     Le Mans Ultimate (LMU_Data)
  providers/iracing.py + session_yaml.py   iRacing (irsdk)
  providers/demo.py    DEMO (sempre marcado is_demo=True)
  core/settings_schema.py  validação das configurações e dos atalhos (sem Qt)
  ui/settings_dialog.py    janela de Configurações (+ painel de layouts)
  core/changelog.py, ui/changelog_dialog.py  janela de novidades (CHANGELOG.md + changelog/)
  core/updater.py, ui/update_ui.py  atualização pelo GitHub (Releases)
  core/module_options.py   opções de cada módulo (janela Config)
  ui/main_window.py        janela principal (menus, abas Módulos/Layouts, bandeja)
  cli.py               diag / snapshot / probe-profile / probe-rest
tests/  (providers, layouts/geometria, camada de UI com Qt simulado)
tools/ui_smoke.py
dados/ (logos, flags, badges, layouts, tracks: dados do usuário)  .github/workflows/release.yml
build_exe/ (launcher, KerbHUD.spec, ícone)  Gerar-exe.bat  requirements-build.txt
config/settings.json
```

## Créditos
Layout de `LMU_Data`: SDK da Studio 397 (header `SharedMemoryInterface.hpp`),
conforme mapeado em pyLMUSharedMemory (MIT, TinyPedal).
