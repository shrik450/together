-- Together database schema
-- Apply with: sqlite3 together.db < schema.sql

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

-- APScheduler tables (created automatically by APScheduler)
-- These are included here for documentation purposes only.
-- APScheduler 4.x will create its own tables when using SQLite data store.
