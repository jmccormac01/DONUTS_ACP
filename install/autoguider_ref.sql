/* old schema*/
CREATE TABLE autoguider_ref (
  field varchar(100) not null primary key,
  telescope varchar(20) not null,
  ref_image varchar(100) not null,
  filter varchar(20) not null,
  valid_from datetime not null,
  valid_until datetime
);

/*Use this command to switch*/
ALTER TABLE autoguider_ref DROP primary key,
ADD ref_id mediumint auto_increment primary key first;

/* New schema*/
CREATE TABLE autoguider_ref (
  ref_id mediumint auto_increment primary key,
  field varchar(100) not null,
  telescope varchar(20) not null,
  ref_image varchar(100) not null,
  filter varchar(20) not null,
  valid_from datetime not null,
  valid_until datetime
);
