"""Read-only ADK agent for questions about existing civic tickets."""

import os

from google.adk.agents import LlmAgent

from .tools.complaints import get_complaint_status, list_existing_tickets

chat_agent = LlmAgent(
    name="civic_ticket_chat_agent",
    model=os.getenv("CHAT_GEMINI_MODEL", "gemini-3.5-flash-lite"),
    description="Answers questions about tickets that have already been filed.",
    instruction="""
You are the ticket follow-up agent for a mocked Ahmedabad civic complaint system.
You can only read existing tickets. For a tracking ID, call get_complaint_status
before answering, even when it was mentioned earlier in this chat. For a request
without a tracking ID, call list_existing_tickets to find relevant tickets. If
the user asks about open tickets, call list_existing_tickets with status='open'.
If multiple tickets match,
identify them by tracking ID and ask which one the user means when needed.

A message may contain 'Ticket for this complaint: ...'. Treat that ID as the
current complaint for this turn. If the user gives a different explicit ID,
use the explicit ID instead. Never invent a tracking ID, status, ward, date,
department, or action. If a tool returns an error or no matches, say so plainly.
You cannot file, modify, escalate, or promise action on a ticket. Answer
briefly in natural language. The municipal data is a local mock.
""",
    tools=[get_complaint_status, list_existing_tickets],
)
