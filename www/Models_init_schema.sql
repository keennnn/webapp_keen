

-- script for Models init
-- Author by: Keen Liu 2018/10/17

DROP database if exists awesome;

create database awesome;
use awesome;

-- grant 普通数据用户，查询、插入、更新、删除 数据库中所有表数据的权利。
grant select, insert, update, delete on awesome.* to 'www-data'@'localhost' identified by 'www-data';

create table users(
	`id` varchar(50) not null,
    `email` varchar(50) not null,
    `passwd` varchar(50) not null,
    `admin` bool not null,
    `name` varchar(50) not null,
    `image` varchar(500) not null,
    `created_at` real not null,
    unique key `idx_email` (`email`),
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=InnoDB default charset=utf8;

create table blogs(
	`id` varchar(50) not null,
    `user_id` varchar(50) not null,
    `user_name` varchar(50) not null,
    `user_image` varchar(500) not null,
    `name` varchar(50) not null,
    `summary` varchar(200) not null,
    `content` mediumtext not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=InnoDB default charset=utf8;


create table comments(
	`id` varchar(50) not null,
    `blog_id` varchar(50) not null,
    `user_id` varchar(50) not null,
    `user_name` varchar(50) not null,
    `user_image` varchar(50) not null,
    `content` mediumtext not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=InnoDB default charset=utf8;








