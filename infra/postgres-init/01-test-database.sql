-- Runs once, the first time the postgres volume is created.
-- The throw-away database used by the `tests` service. Tests drop and recreate its
-- tables, so it must never be the real `kanoon` database.
CREATE DATABASE kanoon_test OWNER kanoon;
