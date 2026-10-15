ALTER TABLE ai_support_tickets
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'new';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ai_support_tickets_status_check'
          AND conrelid = 'ai_support_tickets'::regclass
    ) THEN
        ALTER TABLE ai_support_tickets
            ADD CONSTRAINT ai_support_tickets_status_check
            CHECK (status IN ('new', 'in_progress', 'done', 'rejected'));
    END IF;
END
$$;
