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
ID_Carteira int not null,
ID_Categoria int not null,
foreign key (ID_Carteira) references Carteiras(ID_Carteira),
foreign key (ID_Categoria) references Categorias(ID_Categoria)
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

