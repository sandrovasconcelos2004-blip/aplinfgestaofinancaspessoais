# Gestão Financeira Pessoal

Este documento reúne os requisitos do projeto, organizados por categoria para facilitar a leitura e a evolução futura do sistema.

---

## Requisitos não funcionais

- RNF01: O código deve ser modular e comentários claros, para facilitar a manutenção de funcionalidades.
- RNF02: A interface deve ser simples e intuitiva.
- RNF03: A interface deve estar em português de Portugal e usar euros como moeda.
- RNF04: A persistência dos dados deve ser garantida por uma base de dados MariaDB.
- RNF05: O tratamento de dados deve cumprir com a RGPD.
- RNF06: O front-end deverá ser desenvolvido em HTML e CSS e Python 3.14 usando a framework FLASK 3.1.3
- RNF08: O front-end deve ser encriptado (HTTPS)

## Requisitos funcionais

- RF01: O sistema deve permitir criar uma conta no website, garantindo a privacidade dos dados do utilizador.
- RF02: O sistema deve permitir autenticação com email e palavra-passe, de forma segura.
- RF03: O sistema deve permitir recuperar a conta caso o utilizador se esqueça das credenciais.
- RF04: O sistema deve permitir inserir transações, para acompanhar os gastos.
- RF05: O sistema deve disponibilizar categorias de transações pré-definidas e permitir criar categorias personalizadas.
- RF06: O sistema deve permitir gerir transações de grupo, atribuindo despesas e mostrando o progresso.
- RF07: O sistema deve permitir definir objetivos de poupança.
- RF08: O sistema deve permitir inserir contribuições para cada poupança e mostrar o progresso.
- RF09: O sistema deve permitir eliminar poupanças ou marcá-las como terminadas/realizadas.
- RF10: O sistema deve permitir criar orçamentos.
- RF11: O sistema deve permitir definir orçamentos individuais por categoria (alimentação, lazer, roupa, etc.).
- RF12: O sistema deve mostrar o quão próximo o utilizador está de atingir o orçamento.
- RF13: O sistema deve gerar relatórios simples de gastos e saldos.
- RF14: O sistema deve permitir exportar os relatórios para os poder guardar noutras plataformas.
- RF15: O sistema deve permitir criar grupos para gerir finanças em conjunto.
- RF16: O sistema deve permitir inserir despesas partilhadas e dividi-las por membros específicos do grupo.
