CREATE TABLE autoguider_log (
   updated timestamp default current_timestamp on update current_timestamp,
   reference varchar(50) not null,
   check varchar(50) not null,
   solution_x double not null,
   solution_y double not null,
   culled_max_shift_x varchar(5) not null,
   culled_max_shift_y varchar(5) not null,
   pid_x double not null,
   pid_y double not null,
   std_buff_x double not null,
   std_buff_y double not null   
);

CREATE TABLE autoguider_log_new (
   updated timestamp default current_timestamp on update current_timestamp,
   night date not null,
   reference varchar(150) not null,
   check varchar(150) not null,
   stabilised varchar(5) not null,
   shift_x double not null,
   shift_y double not null,
   pre_pid_x double not null,
   pre_pid_y double not null,
   post_pid_x double not null,
   post_pid_y double not null,
   std_buff_x double not null,
   std_buff_y double not null,
   culled_max_shift_x varchar(5) not null,
   culled_max_shift_y varchar(5) not null
);
