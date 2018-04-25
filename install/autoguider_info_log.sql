CREATE TABLE autoguider_info_log (
   message_id mediumint not null auto_increment primary key,
   updated timestamp default current_timestamp on update current_timestamp,
   telescope varchar(20) not null,
   message varchar(500) not null
);
