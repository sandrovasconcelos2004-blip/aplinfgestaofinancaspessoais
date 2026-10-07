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
