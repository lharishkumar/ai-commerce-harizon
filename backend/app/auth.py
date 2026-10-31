import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Customer

router = APIRouter(prefix="/api/auth", tags=["authentication"])
oauth = OAuth()
if settings.auth0_domain and settings.auth0_client_id:
    oauth.register(name="auth0", client_id=settings.auth0_client_id, client_secret=settings.auth0_client_secret,
                   server_metadata_url=f"https://{settings.auth0_domain}/.well-known/openid-configuration",
                   client_kwargs={"scope": "openid profile email"})


@router.get("/config")
def auth_config():
    return {"mode": settings.auth_mode, "auth0_ready": bool(settings.auth0_domain and settings.auth0_client_id)}


@router.get("/login")
async def login(request: Request):
    if settings.auth_mode == "dev":
        raise HTTPException(400, "Use the local development sign-in button")
    if not settings.auth0_domain or not settings.auth0_client_id or not settings.auth0_client_secret:
        raise HTTPException(503, "Auth0 is not configured")
    request.session["oidc_state"] = secrets.token_urlsafe(24)
    return await oauth.auth0.authorize_redirect(request, settings.auth0_callback_url, state=request.session["oidc_state"])


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    if not hasattr(oauth, "auth0"):
        raise HTTPException(503, "Auth0 is not configured")
    expected = request.session.pop("oidc_state", None)
    if not expected or request.query_params.get("state") != expected:
        raise HTTPException(400, "Invalid authentication state")
    token = await oauth.auth0.authorize_access_token(request)
    profile = token.get("userinfo") or await oauth.auth0.userinfo(token=token)
    if not profile.get("email") or not profile.get("email_verified"):
        raise HTTPException(403, "Please verify your email address with Auth0")
    display_name = (profile.get("name") or " ".join(filter(None, [profile.get("given_name"), profile.get("family_name")]))
                    or profile["email"].split("@", 1)[0]).strip()[:120]
    customer = db.scalar(select(Customer).where(Customer.auth_subject == profile["sub"]))
    if not customer:
        customer = Customer(id=f"cus_{secrets.token_hex(8)}", auth_subject=profile["sub"],
                            display_name=display_name, email=profile["email"], email_verified=True)
        db.add(customer)
    else:
        customer.display_name = display_name
        customer.email = profile["email"]
        customer.email_verified = True
    db.commit()
    request.session["customer_id"] = customer.id
    return RedirectResponse(settings.frontend_url)


@router.post("/dev-login")
def dev_login(request: Request, db: Session = Depends(get_db)):
    if settings.app_env != "development" or settings.auth_mode != "dev":
        raise HTTPException(404, "Not found")
    subject = "local|customer-one"
    customer = db.scalar(select(Customer).where(Customer.auth_subject == subject))
    if not customer:
        customer = Customer(id="cus_local_01", auth_subject=subject, display_name="Local Shopper",
                            email="shopper@example.test", email_verified=True)
        db.add(customer)
        db.commit()
    elif not customer.display_name:
        customer.display_name = "Local Shopper"
        db.commit()
    request.session["customer_id"] = customer.id
    return {"id": customer.id, "name": customer.display_name, "email": customer.email,
            "email_verified": customer.email_verified}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return {"authenticated": False}
    customer = db.get(Customer, customer_id)
    if not customer:
        return {"authenticated": False}
    return {"authenticated": True, "id": customer.id, "name": customer.display_name or customer.email.split("@", 1)[0],
            "email": customer.email, "email_verified": customer.email_verified}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


def require_customer(request: Request, db: Session = Depends(get_db)) -> Customer:
    customer_id = request.session.get("customer_id")
    customer = db.get(Customer, customer_id) if customer_id else None
    if not customer or not customer.email_verified:
        raise HTTPException(401, "Sign in with a verified email to continue")
    return customer
