CREATE TABLE customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE ai_support_tickets (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50),
    issue_summary TEXT NOT NULL,
    urgency VARCHAR(10) NOT NULL,
    database_status VARCHAR(50) NOT NULL,
    action_required VARCHAR(100) NOT NULL,
    raw_email_content TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'new'
        CONSTRAINT ai_support_tickets_status_check
        CHECK (status IN ('new', 'in_progress', 'done', 'rejected'))
);