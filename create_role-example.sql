CREATE DATABASE <your_db_name>;
\c <your_db_name>;

CREATE SCHEMA <your_schema_name>;

CREATE ROLE admin WITH LOGIN PASSWORD '<password>' CREATEROLE;
GRANT ALL ON SCHEMA public, <your_schema_name> TO admin;
GRANT ALL ON ALL TABLES IN SCHEMA public, <your_schema_name> TO admin;
