"""Ticket analysis, customer verification, and PostgreSQL persistence."""

import os
from datetime import date
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv
import requests

load_dotenv()


class UrgencyLevel(str, Enum):
    """Supported urgency classifications assigned during ticket analysis."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TicketStatus(str, Enum):
    """Supported ticket workflow states stored in PostgreSQL."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"


class TicketProcessingError(RuntimeError):
    """Represent a ticket creation failure during analysis, verification, or persistence."""


class TicketNotFoundError(LookupError):
    """Represent a lookup or update request for a ticket that does not exist."""


class SupportTicketSchema(BaseModel):
    """Validate the structured fields extracted from an incoming support email."""

    customer_id: str = Field(description="Die extrahierte Kunden-ID im Format CUST-XXXX.")
    issue_summary: str = Field(description="Prägnante, technische Zusammenfassung des Problems auf Deutsch.")
    urgency: UrgencyLevel = Field(description="Berechnete Dringlichkeit basierend auf Systemausfall oder Business-Impact.")


def get_db_connection():
    """Open a PostgreSQL connection using the configured DB environment variables.

    Returns:
        An open psycopg2 connection.

    Raises:
        RuntimeError: If a required database environment variable is missing.
    """
    required_settings = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing_settings = [
        setting for setting in required_settings if not os.getenv(setting)
    ]
    if missing_settings:
        raise RuntimeError(
            "Missing required database environment variables: "
            + ", ".join(missing_settings)
        )

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=os.getenv("DB_PORT", "5432")
    )

def verify_customer_in_db(customer_id: str) -> bool:
    """Check whether an active customer record exists for the supplied ID.

    Args:
        customer_id: Customer identifier extracted from the ticket text.

    Returns:
        True if an active customer exists; otherwise, False.
    """
    query = "SELECT 1 FROM customers WHERE customer_id = %s AND is_active = TRUE;"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (customer_id,))
            return cur.fetchone() is not None

def save_ticket_to_db(ticket_data: dict, raw_content: str) -> dict:
    """Insert a processed ticket and return its public persisted fields.

    Args:
        ticket_data: Validated analysis fields and customer verification results.
        raw_content: Original support email, retained in the database for internal use.

    Returns:
        The created ticket record, including its ID, status, and processing timestamp.
    """
    query = """
        INSERT INTO ai_support_tickets 
        (customer_id, issue_summary, urgency, database_status, action_required, raw_email_content, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, customer_id, issue_summary, urgency, database_status,
                  action_required, status, processed_at;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (
                ticket_data["customer_id"],
                ticket_data["issue_summary"],
                ticket_data["urgency"],
                ticket_data["database_status"],
                ticket_data["action_required"],
                raw_content,
                TicketStatus.NEW.value,
            ))
            ticket = dict(cur.fetchone())
    ticket["processed_at"] = ticket["processed_at"].isoformat()
    return ticket


def update_ticket_status(ticket_id: int, status: TicketStatus) -> dict:
    """Update a ticket's workflow status and return its ID and new status.

    Args:
        ticket_id: Database identifier of the ticket to update.
        status: New workflow status.

    Returns:
        The ticket ID and updated status.

    Raises:
        TicketNotFoundError: If no ticket has the supplied ID.
    """
    query = """
        UPDATE ai_support_tickets
        SET status = %s
        WHERE id = %s
        RETURNING id, status;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (status.value, ticket_id))
            ticket = cur.fetchone()
            if ticket is None:
                raise TicketNotFoundError(f"Ticket {ticket_id} does not exist")
            return dict(ticket)


def list_tickets(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List tickets in reverse processing order with optional date and page filters.

    Args:
        date_from: Optional inclusive lower processing date.
        date_to: Optional inclusive upper processing date.
        limit: Maximum number of records to return.
        offset: Number of records to skip for pagination.

    Returns:
        Public ticket records without their original email contents.
    """
    conditions = []
    parameters = []
    if date_from is not None:
        conditions.append("processed_at::date >= %s")
        parameters.append(date_from)
    if date_to is not None:
        conditions.append("processed_at::date <= %s")
        parameters.append(date_to)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, customer_id, issue_summary, urgency, database_status,
               action_required, status, processed_at
        FROM ai_support_tickets
        {where_clause}
        ORDER BY processed_at DESC, id DESC
        LIMIT %s OFFSET %s;
    """
    parameters.extend((limit, offset))
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, parameters)
            tickets = [dict(row) for row in cur.fetchall()]
    for ticket in tickets:
        ticket["processed_at"] = ticket["processed_at"].isoformat()
    return tickets


def get_ticket_by_id(ticket_id: int) -> dict:
    """Fetch one public ticket record without exposing its original email.

    Args:
        ticket_id: Database identifier of the requested ticket.

    Returns:
        The public ticket record.

    Raises:
        TicketNotFoundError: If no ticket has the supplied ID.
    """
    query = """
        SELECT id, customer_id, issue_summary, urgency, database_status,
               action_required, status, processed_at
        FROM ai_support_tickets
        WHERE id = %s;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (ticket_id,))
            ticket = cur.fetchone()
            if ticket is None:
                raise TicketNotFoundError(f"Ticket {ticket_id} does not exist")
            result = dict(ticket)
    result["processed_at"] = result["processed_at"].isoformat()
    return result


def generate_ticket_with_ollama(prompt: str) -> dict:
    """Request and validate structured ticket fields from the Ollama service.

    Args:
        prompt: Instructions and support email text to analyze.

    Returns:
        Ticket fields validated against SupportTicketSchema.

    Raises:
        requests.RequestException: If the Ollama request fails.
        pydantic.ValidationError: If Ollama returns invalid ticket data.
    """
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    response = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
            "messages": [{"role": "user", "content": prompt}],
            "format": SupportTicketSchema.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=(5, 300),
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    return SupportTicketSchema.model_validate_json(content).model_dump(mode="json")


def process_incoming_email(email_content: str) -> dict:
    """Analyze an email, verify its customer, and persist the resulting ticket.

    Gemini is attempted when a Gemini API key is configured. Ollama is used
    directly otherwise, or as a fallback when Gemini analysis fails. Unknown
    or inactive customers are flagged for review and assigned high urgency.

    Args:
        email_content: Raw support email text submitted for ticket creation.

    Returns:
        The persisted ticket record, excluding the original email contents.

    Raises:
        TicketProcessingError: If analysis, customer verification, or persistence
            cannot complete.
    """
    print("\n🤖 [Agent] Starte Analyse der unstrukturierten E-Mail...")

    prompt = f"""
    Analysiere die folgende Support-E-Mail als erfahrener System-Architekt.
    Extrahiere die Kunden-ID (Muster: CUST-XXXX). Wenn keine gefunden wird, setze 'UNKNOWN'.
    Fasse das Problem kurz und präzise zusammen.
    
    E-Mail:
    \"\"\"{email_content}\"\"\"
    """

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=30_000,
                    retry_options=types.HttpRetryOptions(
                        attempts=2,
                        initial_delay=1.0,
                        max_delay=5.0,
                    )
                ),
            )
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SupportTicketSchema,
                    temperature=0.0,
                ),
            )
            ticket_data = SupportTicketSchema.model_validate_json(
                response.text
            ).model_dump(mode="json")
            print("✅ Ticketanalyse erfolgreich mit Gemini.")
        except Exception as gemini_error:
            print(
                f"⚠️ Gemini nicht verfügbar ({gemini_error}); "
                "wechsle zu Ollama."
            )
            try:
                ticket_data = generate_ticket_with_ollama(prompt)
            except Exception as ollama_error:
                raise TicketProcessingError(
                    "Ticket analysis failed with Gemini and Ollama"
                ) from ollama_error
    else:
        print("ℹ️ Kein Gemini API-Key konfiguriert; verwende Ollama.")
        try:
            ticket_data = generate_ticket_with_ollama(prompt)
        except Exception as ollama_error:
            raise TicketProcessingError("Ticket analysis failed with Ollama") from ollama_error

    extracted_id = ticket_data["customer_id"]
    print(f"✅ [KI-Extraktion] Erfolgreich strukturiert. Extrahierte ID: {extracted_id}")

    try:
        if extracted_id != "UNKNOWN" and verify_customer_in_db(extracted_id):
            ticket_data["database_status"] = "VERIFIED_EXISTING_CUSTOMER"
            ticket_data["action_required"] = "Direktes Routing in die technische Fachabteilung."
        else:
            ticket_data["database_status"] = "INVALID_OR_UNKNOWN_ID"
            ticket_data["action_required"] = "Eskalation: Account-Management muss Daten prüfen."
            ticket_data["urgency"] = UrgencyLevel.HIGH.value

        ticket = save_ticket_to_db(ticket_data, email_content)
    except Exception as database_error:
        raise TicketProcessingError(
            "Ticket verification or persistence failed"
        ) from database_error

    print(f"💾 Ticket {ticket['id']} persistent gespeichert.")
    return ticket