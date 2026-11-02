create database if not exists trabalho_aplinf;

use trabalho_aplinf;

-- Criação Tabela Utilizadores
create table Utilizadores (
ID_Utilizador int not null auto_increment primary key,
Nome varchar (100) not null,
Apelido varchar (100) not null,
Email varchar (150) unique not null,
Password varchar (255) not null
);

-- Criação Tabela Categorias
create table Categorias (
ID_Categoria int not null auto_increment primary key,
Categoria varchar (100) not null,
ID_Utilizador int null,
foreign key (ID_Utilizador) references Utilizadores(ID_Utilizador),
unique (ID_Utilizador, Categoria)
);


-- Criação Tabela Carteiras
create table Carteiras (
ID_Carteira int not null auto_increment primary key,
Carteira varchar (100) not null,
Valor decimal(12,2) not null default 0.00,
ID_Utilizador int not null,
foreign key (ID_Utilizador) references Utilizadores(ID_Utilizador),
unique (ID_Utilizador, Carteira)
);

-- Criação Tabela Transações
create table Transacoes (
ID_Transacao int not null auto_increment primary key,
Transacao varchar (100) not null,
Tipo enum('receita', 'despesa') not null,
Valor decimal(12,2) not null,
Data datetime not null default current_timestamp,
Aplicada boolean not null default true,
ID_Carteira int not null,
ID_Categoria int not null,
foreign key (ID_Carteira) references Carteiras(ID_Carteira),
foreign key (ID_Categoria) references Categorias(ID_Categoria)
);

-- Criação de Tabela Grupos
create table Grupos (
ID_Grupo int not null auto_increment primary key,
Grupo varchar (100) not null,
Data_Criacao datetime not null default current_timestamp
);

-- Criação de Tabela Funcoes
create table Funcoes (
ID_Funcao int not null auto_increment primary key,
Funcao varchar (20) not null unique
);

-- Criação de Tabela Membro_Grupo
create table Membro_Grupo (
ID_Grupo int not null,
ID_Utilizador int not null,
ID_Funcao int not null,
foreign key (ID_Grupo) references Grupos(ID_Grupo),
foreign key (ID_Utilizador) references Utilizadores(ID_Utilizador),
foreign key (ID_Funcao) references Funcoes(ID_Funcao),
primary key (ID_Grupo, ID_Utilizador)
);

-- Criação de Tabela Convites (convites pendentes para entrar num grupo)
create table Convites (
ID_Convite int not null auto_increment primary key,
ID_Grupo int not null,
ID_Utilizador int not null,
ID_Convidou int not null,
Data datetime not null default current_timestamp,
foreign key (ID_Grupo) references Grupos(ID_Grupo),
foreign key (ID_Utilizador) references Utilizadores(ID_Utilizador),
foreign key (ID_Convidou) references Utilizadores(ID_Utilizador),
unique (ID_Grupo, ID_Utilizador)
);

-- Criação de Tabela Transacoes_Grupo
create table Transacoes_Grupo (
ID_Transacao_Grupo int not null auto_increment primary key,
Transacao varchar (100) not null,
Valor decimal(12,2) not null check (Valor > 0),
Data datetime not null default current_timestamp,
ID_Grupo int not null,
ID_Categoria int not null,
ID_Utilizador int not null,
ID_Transacao_Pessoal int null unique,
foreign key (ID_Grupo) references Grupos(ID_Grupo),
foreign key (ID_Categoria) references Categorias(ID_Categoria),
foreign key (ID_Utilizador) references Utilizadores(ID_Utilizador),
foreign key (ID_Transacao_Pessoal) references Transacoes(ID_Transacao)
);


-- Criação de Tabela Membros_Transacoes_Grupo
create table Membros_Transacoes_Grupo (
ID_Transacao_Grupo int not null,
ID_Utilizador int not null,
Valor decimal(12,2) not null check (Valor > 0),
Pago boolean not null default false,
Data_Pagamento datetime null,
ID_Transacao_Pagamento int null unique,
ID_Transacao_Recebimento int null unique,
foreign key (ID_Transacao_Grupo) references Transacoes_Grupo(ID_Transacao_Grupo),
foreign key (ID_Utilizador) references Utilizadores(ID_Utilizador),
foreign key (ID_Transacao_Pagamento) references Transacoes(ID_Transacao),
foreign key (ID_Transacao_Recebimento) references Transacoes(ID_Transacao),
primary key (ID_Transacao_Grupo, ID_Utilizador)
);

-- Categorias pré-definidas (comuns a todos os utilizadores)
insert into Categorias (Categoria, ID_Utilizador) values
('Saldo Inicial', null),
('Alimentação', null),
('Casa', null),
('Lazer', null),
('Salário', null),
('Saúde', null),
('Transportes', null),
('Outros', null);

-- Funções dos membros de um grupo
insert into Funcoes (Funcao) values ('Administrador'), ('Membro');
