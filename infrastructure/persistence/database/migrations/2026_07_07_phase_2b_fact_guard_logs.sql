-- Phase 2B: storyos_fact_guard_logs audit table
-- Records every fact_guard attempt (sflog × 2 + prose × 1) per chapter
-- so writers can review LLM activity via Phase 2C UI.

CREATE TABLE IF NOT EXISTS storyos_fact_guard_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id        INTEGER NOT NULL,
    chapter_number    INTEGER NOT NULL,
    novel_id          TEXT NOT NULL,
    attempt           INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
    mode              TEXT NOT NULL CHECK (mode IN ('sflog', 'prose')),
    action            TEXT NOT NULL CHECK (action IN (
        'passed',
        'rewritten_sflog',
        'no_rewrite_sflog',
        'rewritten_prose',
        'forced_pass_rollback_llm',
        'rolled_back_regression',
        'provider_failed',
        'node_missing'
    )),
    hard_before       INTEGER NOT NULL DEFAULT 0,
    hard_after        INTEGER NOT NULL DEFAULT 0,
    rule_id           TEXT,
    severity          TEXT,
    diff_excerpt      TEXT,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (chapter_id)  REFERENCES chapters(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fact_guard_logs_novel_created
    ON storyos_fact_guard_logs (novel_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fact_guard_logs_chapter
    ON storyos_fact_guard_logs (chapter_id, attempt);