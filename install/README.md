# Io setup - mirror onto other machines

Install miniconda3-latest (python3)
conda install numpy
conda install scipy
conda install astropy
conda install scikit-image
conda install pymysql
Install Github Desktop
Install Visual Studio C++ 2013 redistributable package
Install mysql (custom: server, utils, shell + workbench only)
pip install donuts (or install from source)

CREATE TABLE autoguider_ref (
  field varchar(100) not null primary key,
  telescope varchar(20) not null,
  ref_image varchar(100) not null,
  filter varchar(20) not null,
  valid_from datetime not null,
  valid_until datetime
);

CREATE TABLE autoguider_log (
   updated timestamp default current_timestamp on update current_timestamp,
   reference varchar(100) not null,
   comparison varchar(100) not null,
   solution_x double not null,
   solution_y double not null,
   culled_max_shift_x varchar(5) not null,
   culled_max_shift_y varchar(5) not null,
   pid_x double not null,
   pid_y double not null,
   std_buff_x double not null,
   std_buff_y double not null
);

To access the database manually fire up the mysql shell. Turn it to SQL mode with \sql.
Then connect to the server with \c localhost. Enter user the password above. Then navigate the db as normal with typical SQL syntax.

