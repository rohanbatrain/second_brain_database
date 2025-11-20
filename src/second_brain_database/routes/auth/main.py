import os
from typing import Optional

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Initialize Jinja2 templates. Templates are located in the "templates" folder next to this file.
_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_templates_dir)


def render_email_verification_page(
    request: Request, success: bool = True, message: Optional[str] = None
) -> HTMLResponse:
    """
    Render the email verification page using Jinja2 templates.

    Args:
        request: FastAPI Request object (required by TemplateResponse)
        success: boolean flag indicating verification status
        message: optional custom message to display

    Returns:
        TemplateResponse which becomes an HTMLResponse when returned from FastAPI route
    """
    default_message = "Email Verified Successfully!" if success else "Email Verification Failed"
    display_message = message or default_message

    context = {
        "request": request,
        "success": bool(success),
        "display_message": display_message,
    }

    return templates.TemplateResponse("verification.html", context)
