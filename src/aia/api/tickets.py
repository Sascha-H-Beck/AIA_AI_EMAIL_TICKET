"""REST endpoints and request/response models for ticket operations."""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from aia.main import (
    TicketNotFoundError,
    TicketProcessingError,
    TicketStatus,
    get_ticket_by_id,
    list_tickets,
    process_incoming_email,
    update_ticket_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tickets", tags=["tickets"])


class TicketResponse(BaseModel):
    """Ticket fields returned by creation and list endpoints."""

    id: int
    customer_id: str
    company_name: str | None
    issue_summary: str
    urgency: str
    database_status: str
    action_required: str
    status: TicketStatus
    processed_at: str


class TicketDetailResponse(TicketResponse):
    """Full ticket representation returned by the detail endpoint."""

    raw_email_content: str


class CreateTicketRequest(BaseModel):
    """Validate text submitted to create and analyze a support ticket."""

    email_content: str = Field(min_length=1, max_length=30000)


class UpdateTicketStatusRequest(BaseModel):
    """Validate a requested ticket workflow status change."""

    status: TicketStatus


class TicketStatusResponse(BaseModel):
    """Response containing a ticket identifier and its updated status."""

    id: int
    status: TicketStatus


@router.get("", response_model=list[TicketResponse], operation_id="getTickets")
def get_tickets(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List tickets with optional inclusive date filters and pagination.

    Raises:
        HTTPException: If the date range starts after it ends.
    """
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from must be on or before date_to",
        )
    return list_tickets(date_from, date_to, limit, offset)


@router.get(
    "/{ticket_id}",
    response_model=TicketDetailResponse,
    operation_id="getTicketByID",
)
def get_ticket(ticket_id: int) -> dict:
    """Return full ticket details by ID or report that it does not exist.

    Args:
        ticket_id: Identifier of the requested ticket.

    Raises:
        HTTPException: With status 404 if the ticket does not exist.
    """
    try:
        return get_ticket_by_id(ticket_id)
    except TicketNotFoundError as error:
        raise HTTPException(status_code=404, detail="Ticket not found") from error


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="postTickets",
)
def post_ticket(request: CreateTicketRequest) -> dict:
    """Analyze submitted email text and create a persisted ticket.

    Args:
        request: Validated ticket creation payload.

    Raises:
        HTTPException: With status 503 if ticket processing fails.
    """
    try:
        return process_incoming_email(request.email_content)
    except TicketProcessingError as error:
        logger.exception("Ticket processing failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticket processing failed. Check service logs and try again.",
        ) from error


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketStatusResponse,
    operation_id="updateTicketStatus",
)
def patch_ticket_status(
    ticket_id: int,
    request: UpdateTicketStatusRequest,
) -> dict:
    """Update a ticket's workflow status.

    Args:
        ticket_id: Identifier of the ticket to update.
        request: Validated target status.

    Raises:
        HTTPException: With status 404 if the ticket does not exist.
    """
    try:
        return update_ticket_status(ticket_id, request.status)
    except TicketNotFoundError as error:
        raise HTTPException(status_code=404, detail="Ticket not found") from error
