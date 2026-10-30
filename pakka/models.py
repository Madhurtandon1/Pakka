from typing import Literal, Optional

from pydantic import BaseModel, Field

# "kyc" is the Aadhaar e-KYC step; "pan", "selfie" and "mandate" (auto-pay) were added for the
# document steps. Existing step names are unchanged.
Step = Literal["basic", "pan", "kyc", "selfie", "bank", "mandate", "offer", "review"]

EventType = Literal[
    "step_view",
    "upload_ok",
    "upload_failed",
    "liveness_failed",
    "digilocker_error",
    "kfs_open",
    "back",
    "session_expired",
    "submit",
    # document steps: a format/verification check failed or passed (the code says which)
    "check_failed",
    "check_ok",
]


class Event(BaseModel):
    type: EventType
    step: Step
    ts: float = Field(ge=0)
    code: Optional[str] = None


class Detection(BaseModel):
    stalled: bool
    blocker: Optional[str] = None
    step: Optional[str] = None
    code: Optional[str] = None
    reasons: list[str] = []


class Rescue(BaseModel):
    journey_id: str
    detection: Detection
    action: Optional[str] = None
    needs_consent: bool = False
    message: Optional[str] = None
    lang: str = "en"
    escalated: bool = False
    policy_ok: bool = True
    latency_ms: float = 0.0
