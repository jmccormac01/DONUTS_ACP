
/* New schema*/
CREATE TABLE autoguider_ref (
  ref_id mediumint not null auto_increment primary key,
  field varchar(100) not null,
  telescope varchar(20) not null,
  ref_image varchar(100) not null,
  filter varchar(20) not null,
  valid_from datetime not null,
  valid_until datetime
);

/* old schema*/
CREATE TABLE autoguider_ref (
  field varchar(100) not null primary key,
  telescope varchar(20) not null,
  ref_image varchar(100) not null,
  filter varchar(20) not null,
  valid_from datetime not null,
  valid_until datetime
);
