# Relatório de Conclusão do Sprint 01

**Projeto:** Sistema de Gestão Financeira Pessoal  
**Unidade Curricular:** [Aplicações Informáticas]  
**Data de Termino do Sprint:** 8 de outubro de 2026  
**Equipa:**
* Filipe Santos, 2240582
* Leonor Leitão, 2241007
* Sandro Vasconcelos, 2241106

---

## 1. Visão Geral e Objetivos do Sprint

O principal objetivo do **Sprint 01** focou-se no planeamento inicial do projeto, estabelecimento do fluxo de trabalho Scrum, definição dos requisitos de engenharia de software e na preparação do ambiente de desenvolvimento e infraestrutura (VM, base de dados e repositório).

### Metas Definidas:
* Levantamento e formalização dos Requisitos Funcionais (RF) e Não Funcionais (RNF).
* Estruturação do Product Backlog e seleção das tarefas do primeiro ciclo.
* Configuração do repositório no GitHub e controlo de versões.
* Aprovisionamento da Máquina Virtual (VM) e instalação da stack tecnológica.
* Definição de normas de qualidade através da *Definition of Done* (DoD).
* Modelação dos processos iniciais e casos de uso da aplicação.

---

## 2. Requisitos do Sistema

### 2.1. Requisitos Não Funcionais (RNF)
* **RNF01:** O código deve ser modular e incluir comentários claros para facilitar a manutenção.
* **RNF02:** A interface deve ser simples e intuitiva.
* **RNF03:** A interface deve estar em português de Portugal (pt-PT) e utilizar euros (€) como moeda.
* **RNF04:** A persistência dos dados deve ser assegurada por uma base de dados MariaDB.
* **RNF05:** O tratamento de dados deve cumprir integralmente com o RGPD.
* **RNF06:** O front-end deverá ser desenvolvido em HTML, CSS e Python 3.14 utilizando a framework Flask 3.1.3.
* **RNF08:** O tráfego do front-end deve ser encriptado via HTTPS.

### 2.2. Requisitos Funcionais (RF para o ciclo inicial)
* **RF01 a RF03:** Gestão de utilizadores (criação de conta segura, autenticação e recuperação de credenciais).
* **RF04 e RF05:** Registo de transações e gestão de categorias personalizadas.
* **RF06 a RF16:** Funcionalidades de poupança, orçamentos individuais e despesas partilhadas em grupo.

---

## 3. Definition of Done (DoD)

Para assegurar a qualidade e conformidade das entregas, foram estabelecidos os seguintes critérios obrigatórios para a conclusão de qualquer item de trabalho:

* **Padrões de Código:** Arquitetura modular em Flask, remoção de código gerado por IA não validado e parâmetros seguros em SQL contra injeções.
* **Ambiente e Configuração:** Variáveis sensíveis e credenciais isoladas em ficheiro `.env`.
* **Localização e Formatação:** Textos integralmente em pt-PT e valores em euros (€).
* **Segurança:** Comunicação via HTTPS, hashing de palavras-passe e respeito pelo RGPD.
* **Execução e Testes:** Código validado e a correr sem falhas no ambiente da VM.
* **Revisão e Integração:** Revisão por pares (*peer review*) e commits no ramo correto do repositório GitHub.

## 4. Arquitetura e Ambiente Técnico

* **Linguagem / Framework:** Python 3.14 com Flask 3.1.3
* **Base de Dados:** MariaDB
* **Segurança:** Encriptação HTTPS e proteção de variáveis de ambiente
* **Ambiente de Execução:** Máquina Virtual dedicada para simulação de produção
* **Ferramentas de Modelação:** SAP Signavio Academic Edition (BPMN 2.0) e diagramas de Use Cases

---

## 5. Retspetiva do Sprint (*Sprint Retrospective*)

### O que correu bem:
* Rápido alinhamento na definição dos requisitos funcionais e arquitetura.
* Utilização eficaz de prompts de IA para aceleração do esqueleto do código inicial.
* Criação antecipada da VM e definição clara da *Definition of Done*.

### Desafios encontrados:
* Configuração e arranque do ambiente na Máquina Virtual (VM)
* Necessidade de refatoração do código sugerido pela IA para cumprir estritamente os padrões modulares do Flask e parâmetros da MariaDB.
* Ajustes nos certificados para garantir HTTPS na VM local.

### Melhorias para o Sprint 02:
* Distribuir a autoria dos commits de forma mais contínua ao longo das semanas.
* Iniciar os testes unitários mais cedo no ciclo do sprint.
