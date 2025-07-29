-- File: tests/schemas/simple_blog.sql
-- A simple schema for testing the generator

-- Drop tables if they exist (optional, good for rerunning tests)
DROP TABLE IF EXISTS post;
DROP TABLE IF EXISTS author;

-- Author Table
CREATE TABLE author (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    bio TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);

-- Add some basic data
INSERT INTO author (name, email, bio) VALUES
  ('Alice Author', 'alice@example.com', 'Writes about tech.'),
  ('Bob Blogger', 'bob@example.com', NULL);


-- Post Table
CREATE TABLE post (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(210) UNIQUE NOT NULL,
    content TEXT,
    published_date DATE,
    author_id INTEGER NOT NULL REFERENCES author(id) ON DELETE CASCADE,
    status VARCHAR(10) DEFAULT 'draft',
    read_count INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX post_author_id_idx ON post (author_id);
CREATE INDEX post_published_date_idx ON post (published_date DESC);
-- Example multi-column index
CREATE INDEX post_author_status_idx ON post (author_id, status);
-- Example unique index (will become UniqueConstraint in Django >= 2.2)
CREATE UNIQUE INDEX post_slug_lc_idx ON post (LOWER(slug));

-- Add some basic data
INSERT INTO post (title, slug, content, published_date, author_id, status, read_count) VALUES
  ('First Post by Alice', 'first-post-by-alice', 'Content for the first post.', '2023-01-15', 1, 'published', 100),
  ('Draft by Bob', 'draft-by-bob', 'This is just a draft.', NULL, 2, 'draft', 5);

-- Example multi-column unique constraint (will become UniqueConstraint)
ALTER TABLE post ADD CONSTRAINT post_author_title_uniq UNIQUE (author_id, title);
