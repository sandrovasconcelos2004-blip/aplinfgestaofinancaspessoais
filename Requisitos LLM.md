# Finances4You - Gestão Financeira Pessoal


Este documento reúne os requisitos do projeto, organizados por categoria para facilitar a leitura e a evolução futura do sistema.

---

## Requisitos não funcionais

- RNF01: O código deve ser modular e documentado, para facilitar a adição de funcionalidades.
- RNF02: A interface deve ser simples e intuitiva.
- RNF03: A interface deve estar em português de Portugal e usar euros como moeda.
- RNF04: A persistência dos dados deve ser garantida por uma base de dados MariaDB.
- RNF05: O tratamento de dados deve cumprir com a RGPD.
- RNF06: O front-end deverá ser desenvolvido em HTML e CSS.
- RNF07: O front-end deve estar acessível via internet.
- RNF08: O front-end deve ser encriptado (HTTPS).
- RNF09: O back-end deve ser desenvolvido em Python com a framework Flask.
- RNF10: As palavras-passe nunca são guardadas em texto simples, apenas com hash.
- RNF11: As credenciais (base de dados, SMTP, chave secreta) são guardadas em ficheiro .env e não no código.
- RNF12: Cada utilizador só pode ver e alterar os seus próprios dados (carteiras, transações, categorias, grupos de que é membro).
- RNF13: As operações que mexem em várias tabelas são atómicas, ou seja, ou ficam todas gravadas ou nenhuma fica.
- RNF14: Os valores monetários são guardados com 2 casas decimais e o formulário aceita vírgula ou ponto.
- RNF15: O sistema não revela se um email está registado. Na recuperação de conta e nos convites aparece sempre a mesma mensagem.
- RNF16: O sistema envia emails por SMTP com TLS.

## Regras de escrita de código

- Código em Python 3.14.
- Notação de variáveis em snake notation.
- Nomes de variáveis, funcções e rotas em português.
- Cada função e rota tem uma docstring a explicar o que faz.
- Consultas SQL sempre parametrizadas, nunca com o texto concatenado, para evitar SQL injection.
- Nomes de tabelas e colunas na base de dados em PascalCase com '_'.

---

## Requisitos funcionais

- RF01: O sistema deve permitir criar uma conta no website, garantindo a privacidade dos dados do utilizador.
- RF02: O sistema deve permitir autenticação com email e palavra-passe, de forma segura.
- RF03: O sistema deve permitir recuperar a conta caso o utilizador se esqueça das credenciais.
- RF04: O sistema deve permitir inserir transações de receita ou despesa, para acompanhar os gastos.
- RF05: O sistema deve disponibilizar categorias de transações pré-definidas e permitir criar categorias personalizadas.
- RF06: O sistema deve permitir definir objetivos de poupança.
- RF07: O sistema deve permitir inserir contribuições para cada poupança e mostrar o progresso.
- RF08: O sistema deve permitir eliminar poupanças ou marcá-las como terminadas/realizadas.
- RF09: O sistema deve permitir criar orçamentos.
- RF10: O sistema deve permitir definir orçamentos individuais por categoria (alimentação, lazer, roupa, etc.).
- RF11: O sistema deve mostrar o quão próximo o utilizador está de atingir o orçamento.
- RF12: O sistema deve gerar relatórios simples de gastos e saldos.
- RF13: O sistema deve permitir exportar os relatórios para os poder guardar noutras plataformas.
- RF14: O sistema deve permitir criar grupos para gerir finanças em conjunto.
- RF15: O sistema deve permitir inserir despesas partilhadas e dividi-las por membros específicos do grupo.
- RF16: O sistema deve permitir criar carteiras com nome e valor inicial.
- RF17: O sistema deve permitir ver as carteiras e o saldo de cada uma, e mudar de carteira na área pessoal.
- RF18: O sistema deve permitir editar uma transação (descrição, valor, categoria e data), com o saldo acertado pela diferença.
- RF19: O sistema deve permitir eliminar uma transação, revertendo o efeito que teve no saldo.
- RF20: O sistema deve permitir agendar transações com data futura. Só alteram o saldo quando chega essa data.
- RF21: O sistema deve permitir filtrar as transações por mês.
- RF22: O sistema deve impedir despesas que deixem o saldo da carteira negativo.
- RF23: O sistema deve impedir 'editar' e 'eliminar' a transação 'Saldo Inicial' e as transações de grupos.
- RF24: O sistema deve permitir o administrador convidar utilizadores pelo email.
- RF25: O sistema deve permitir o utilizador aceitar ou recusar os convites pendentes.
- RF26: O sistema deve permitir o administrador remover membros, exceto quem ainda tem partes por pagar ou por receber. O administrador não se pode remover a si próprio.
- RF27: O sistema deve permitir cada membro pagar a sua parte de uma despesa de grupo.
- RF28: O sistema deve permitir ver os membros do grupo.
- RF29: O sistema deve permitir filtrar as despesas do grupo por mês.
- RF30: O sistema deve impedir que despesas de grupo tenham data futura.
