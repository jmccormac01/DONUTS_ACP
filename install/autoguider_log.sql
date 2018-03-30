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