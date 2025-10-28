-- Phase 1: Multi-User Backend Migration
-- Creates users and clipper_cards tables
-- Adds user_id columns to existing tables

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Create index on email for fast lookups
CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);

-- Create clipper_cards table
CREATE TABLE IF NOT EXISTS clipper_cards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    card_number TEXT NOT NULL,
    rider_name TEXT NOT NULL,
    credentials_encrypted TEXT,
    is_primary INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create unique constraint on user_id + card_number
CREATE UNIQUE INDEX IF NOT EXISTS clipper_cards_user_card_idx
    ON clipper_cards(user_id, card_number);

-- Create index on user_id for fast lookups
CREATE INDEX IF NOT EXISTS clipper_cards_user_id_idx ON clipper_cards(user_id);

-- Add user_id column to riders table (for backward compatibility)
-- This column will link existing rider data to new user accounts
-- Note: This is idempotent - only adds column if it doesn't exist

-- Add user_id column to trips table for row-level security
-- Note: In SQLite, we need to check if column exists before adding
-- This is handled by the migration script logic

-- Note: The actual ALTER TABLE commands will be executed conditionally
-- in the Python migration script to handle existing data gracefully
