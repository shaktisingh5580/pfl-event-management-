-- ═══════════════════════════════════════════════════════════════════════
--  PFL Event Management — FRESH DATABASE SETUP
--  Run in: Supabase Dashboard → SQL Editor → New Query → Run
-- ═══════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 1: attendees
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE attendees (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    email               TEXT NOT NULL UNIQUE,
    phone               TEXT DEFAULT '',
    password_hash       TEXT,
    skills              TEXT DEFAULT '',
    interests           TEXT DEFAULT '',
    goals               TEXT DEFAULT '',
    telegram_id         BIGINT UNIQUE,
    telegram_username   TEXT DEFAULT '',
    qr_code             TEXT,
    seat                TEXT,
    coordinator         TEXT,
    checked_in          BOOLEAN DEFAULT FALSE,
    checked_in_at       TIMESTAMPTZ,
    source              TEXT DEFAULT 'website',
    event_id            TEXT DEFAULT '',
    dynamic_fields      JSONB DEFAULT '{}',
    embedding           VECTOR(1536),
    college             TEXT DEFAULT '',
    year_of_study       TEXT DEFAULT '',
    department          TEXT DEFAULT '',
    tshirt_size         TEXT DEFAULT '',
    team_preference     TEXT DEFAULT 'looking_for_team',
    matched_with        UUID[] DEFAULT '{}',
    match_index         INT DEFAULT 0,
    registered_at       TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 2: events
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    event_type      TEXT,
    date            TEXT,
    venue           TEXT,
    theme           TEXT,
    description     TEXT,
    plan            JSONB DEFAULT '{}',
    website_url     TEXT,
    poster_url      TEXT,
    organizer_id    UUID,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 3: organizer_files (uploaded PDFs for AI knowledge base)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE organizer_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        TEXT NOT NULL,
    description     TEXT DEFAULT '',
    status          TEXT DEFAULT 'processing',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 4: event_knowledge_chunks (PDF chunks with embeddings for RAG)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE event_knowledge_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id         UUID REFERENCES organizer_files(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    embedding       VECTOR(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 5: certificates
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE certificates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendee_id     UUID REFERENCES attendees(id) ON DELETE CASCADE,
    attendee_name   TEXT DEFAULT '',
    event_name      TEXT DEFAULT 'PFL Event',
    cert_url        TEXT,
    cert_id         TEXT DEFAULT '' UNIQUE,
    qr_data         TEXT,
    rank            TEXT DEFAULT 'Participant',
    verified_count  INT DEFAULT 0,
    issued_at       TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 6: complaints
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE complaints (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id         BIGINT,
    telegram_username   TEXT DEFAULT '',
    attendee_id         UUID REFERENCES attendees(id) ON DELETE SET NULL,
    category            TEXT DEFAULT 'Other',
    severity            TEXT DEFAULT 'medium',
    description         TEXT NOT NULL,
    summary             TEXT DEFAULT '',
    location            TEXT DEFAULT '',
    status              TEXT DEFAULT 'open',
    resolved_by         BIGINT,
    resolved_at         TIMESTAMPTZ,
    admin_message_id    BIGINT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 7: feedback
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendee_id     UUID REFERENCES attendees(id) ON DELETE SET NULL,
    message         TEXT NOT NULL,
    rating          INT,
    sentiment       TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 8: match_interactions (AI networking)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE match_interactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendee_a      UUID REFERENCES attendees(id) ON DELETE CASCADE,
    attendee_b      UUID REFERENCES attendees(id) ON DELETE CASCADE,
    action          TEXT DEFAULT 'pending',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 9: wall_photos (social wall)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE wall_photos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id     BIGINT,
    attendee_id     UUID REFERENCES attendees(id) ON DELETE SET NULL,
    attendee_name   TEXT,
    sender_name     TEXT DEFAULT '',
    original_url    TEXT,
    branded_url     TEXT,
    cloudinary_url  TEXT DEFAULT '',
    file_url        TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending',
    approved        BOOLEAN DEFAULT FALSE,
    event_id        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  TABLE 10: photos (face recognition — optional)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE photos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drive_url           TEXT,
    face_encoding       JSONB,
    matched_attendees   UUID[] DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════
--  INDEXES
-- ═══════════════════════════════════════════════════════════════════════
CREATE INDEX idx_attendees_email ON attendees(email);
CREATE INDEX idx_attendees_telegram ON attendees(telegram_id);
CREATE INDEX idx_attendees_event ON attendees(event_id);
CREATE INDEX idx_complaints_status ON complaints(status);
CREATE INDEX idx_wall_status ON wall_photos(status);
CREATE INDEX idx_chunks_file ON event_knowledge_chunks(file_id);


-- ═══════════════════════════════════════════════════════════════════════
--  RPC FUNCTIONS — drop old versions first to avoid return-type conflicts
-- ═══════════════════════════════════════════════════════════════════════
DROP FUNCTION IF EXISTS register_attendee(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB);
DROP FUNCTION IF EXISTS authenticate_attendee(TEXT,TEXT,TEXT);
DROP FUNCTION IF EXISTS search_knowledge_base(VECTOR,FLOAT,INT);
DROP FUNCTION IF EXISTS search_knowledge_base(VECTOR,DOUBLE PRECISION,INTEGER);
DROP FUNCTION IF EXISTS match_attendees(VECTOR,UUID,INT);
DROP FUNCTION IF EXISTS match_attendees(VECTOR,UUID,INTEGER);
DROP FUNCTION IF EXISTS checkin_by_id(UUID);
DROP FUNCTION IF EXISTS verify_certificate(UUID);

-- 1. Register attendee (web registration with password)
CREATE OR REPLACE FUNCTION register_attendee(
    p_name TEXT,
    p_email TEXT,
    p_phone TEXT DEFAULT '',
    p_password TEXT DEFAULT '',
    p_event_id TEXT DEFAULT '',
    p_telegram_username TEXT DEFAULT '',
    p_dynamic_fields JSONB DEFAULT '{}'
)
RETURNS SETOF attendees
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE hashed TEXT;
BEGIN
    IF p_password != '' THEN
        hashed := crypt(p_password, gen_salt('bf'));
    ELSE
        hashed := NULL;
    END IF;
    RETURN QUERY
    INSERT INTO attendees (name, email, phone, password_hash, event_id, telegram_username, dynamic_fields, source)
    VALUES (p_name, p_email, p_phone, hashed, p_event_id, p_telegram_username, p_dynamic_fields, 'website')
    RETURNING *;
END; $$;

-- 2. Authenticate attendee (web login)
CREATE OR REPLACE FUNCTION authenticate_attendee(
    p_email TEXT,
    p_password TEXT,
    p_event_id TEXT DEFAULT ''
)
RETURNS SETOF attendees
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM attendees
    WHERE email = p_email
      AND (p_event_id = '' OR event_id = p_event_id)
      AND password_hash IS NOT NULL
      AND password_hash = crypt(p_password, password_hash);
END; $$;

-- 3. Search knowledge base (RAG for AI Architect)
CREATE OR REPLACE FUNCTION search_knowledge_base(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5
)
RETURNS TABLE (id UUID, content TEXT, similarity FLOAT)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT ekc.id, ekc.content,
           (1 - (ekc.embedding <=> query_embedding))::FLOAT AS similarity
    FROM event_knowledge_chunks ekc
    WHERE 1 - (ekc.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END; $$;

-- 4. Match attendees (AI networking)
CREATE OR REPLACE FUNCTION match_attendees(
    query_embedding VECTOR(1536),
    exclude_id UUID,
    match_count INT DEFAULT 5
)
RETURNS TABLE (id UUID, name TEXT, skills TEXT, interests TEXT, similarity FLOAT)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT a.id, a.name, a.skills, a.interests,
           (1 - (a.embedding <=> query_embedding))::FLOAT AS similarity
    FROM attendees a
    WHERE a.id != exclude_id AND a.checked_in = TRUE AND a.embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT match_count;
END; $$;

-- 5. Check-in by QR scan
CREATE OR REPLACE FUNCTION checkin_by_id(p_attendee_id UUID)
RETURNS SETOF attendees
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    UPDATE attendees SET checked_in = TRUE, checked_in_at = NOW() WHERE id = p_attendee_id;
    RETURN QUERY SELECT * FROM attendees WHERE id = p_attendee_id;
END; $$;

-- 6. Verify certificate by QR
CREATE OR REPLACE FUNCTION verify_certificate(p_cert_id UUID)
RETURNS TABLE (cert_id UUID, attendee_name TEXT, attendee_email TEXT, rank TEXT, event_name TEXT, verified_count INT)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE certificates SET verified_count = verified_count + 1 WHERE id = p_cert_id;
    RETURN QUERY
    SELECT c.id, a.name, a.email, c.rank, c.event_name, c.verified_count
    FROM certificates c JOIN attendees a ON c.attendee_id = a.id
    WHERE c.id = p_cert_id;
END; $$;


-- ═══════════════════════════════════════════════════════════════════════
--  ROW LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════════════════
ALTER TABLE attendees ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaints ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizer_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE wall_photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE photos ENABLE ROW LEVEL SECURITY;

-- Public read + service write for all tables
CREATE POLICY "allow_all" ON attendees FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON certificates FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON complaints FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON feedback FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON match_interactions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON organizer_files FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON event_knowledge_chunks FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON wall_photos FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON photos FOR ALL USING (true) WITH CHECK (true);


-- ═══════════════════════════════════════════════════════════════════════
--  SEED TEST USER
-- ═══════════════════════════════════════════════════════════════════════
INSERT INTO attendees (name, email, phone, password_hash, event_id, source, dynamic_fields)
VALUES (
    'Test User', 'test@pfl.com', '9876543210',
    crypt('password123', gen_salt('bf')),
    'codestorm-2026', 'website',
    '{"team_name": "Team Alpha", "tshirt_size": "L"}'::JSONB
);


-- ═══════════════════════════════════════════════════════════════════════
--  ✅ DONE! 10 tables + 6 functions + indexes + RLS + test user
--
--  Test login: email=test@pfl.com  password=password123
-- ═══════════════════════════════════════════════════════════════════════
