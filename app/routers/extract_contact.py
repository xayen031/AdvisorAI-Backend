# app/routers/contact_extractor.py
import logging
import os
import re
import json
from datetime import datetime
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from openai import AsyncOpenAI

from app.deps import get_user_session
from app.db import supabase

router = APIRouter()
logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Request/Response Models ---
class Message(BaseModel):
    speaker: str
    text: str

class ExtractContactRequest(BaseModel):
    messages: List[Message]

class FamilyMemberModel(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    relationship: Optional[str] = None

class PersonalDetailsModel(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    dateOfBirth: Optional[datetime] = None
    otherDetails: Optional[str] = None

class FinancialsModel(BaseModel):
    income: Optional[str] = None
    expenditure: Optional[str] = None
    assets: Optional[str] = None
    liabilities: Optional[str] = None
    emergencyFund: Optional[str] = None
    investments: Optional[str] = None
    protection: Optional[str] = None
    retirementSavings: Optional[str] = None
    estatePlanning: Optional[str] = None

class SpouseModel(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None

class FamilyInfoModel(BaseModel):
    maritalStatus: Optional[str] = None
    spouse: Optional[SpouseModel] = None
    children: Optional[List[FamilyMemberModel]] = None
    parents: Optional[List[FamilyMemberModel]] = None
    siblings: Optional[List[FamilyMemberModel]] = None

class RiskProfileModel(BaseModel):
    riskTolerance: Optional[str] = None
    investmentHorizon: Optional[str] = None
    investmentObjectives: Optional[str] = None
    appetiteForRisk: Optional[str] = None
    investmentFocus: Optional[str] = None
    investmentStyle: Optional[str] = None
    esgInterests: Optional[str] = None

class ContactModel(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None
    lastContact: Optional[datetime] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    personalDetails: Optional[PersonalDetailsModel] = None
    financials: Optional[FinancialsModel] = None
    family: Optional[FamilyInfoModel] = None
    riskProfile: Optional[RiskProfileModel] = None

# --- Utility to normalize fields ---
def normalize_string_fields(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: (
                v if isinstance(v, str)
                else json.dumps(v) if isinstance(v, (dict, list))
                else str(v) if v is not None else None
            )
            for k, v in obj.items()
        }
    return obj

# --- Endpoint ---
@router.post("/extract_contact", response_model=ContactModel, response_model_exclude_none=True)
async def extract_contact(payload: ExtractContactRequest, session_info=Depends(get_user_session)):
    transcript = "\n".join(f"{m.speaker}: {m.text}" for m in payload.messages)
    prompt = (
        "Extract contact information from the meeting transcript. "
        "Return ONLY valid JSON matching our Contact schema.\n"
        f"Transcript:\n{transcript}"
    )
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are a service that extracts structured contact info "
                    "from conversation transcripts. Output strict JSON."
                )},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content).strip()
        if not content:
            raise HTTPException(status_code=500, detail="Empty response from extraction service.")
        data = json.loads(content)

        if 'financials' in data and isinstance(data['financials'], dict):
            data['financials'] = normalize_string_fields(data['financials'])
        if 'riskProfile' in data and isinstance(data['riskProfile'], dict):
            data['riskProfile'] = normalize_string_fields(data['riskProfile'])
        if 'family' in data and isinstance(data['family'], dict):
            fam = data['family']
            for key in ('parents', 'children', 'siblings'):
                if key in fam and isinstance(fam[key], dict):
                    fam[key] = list(fam[key].values())
            data['family'] = fam

        contact = ContactModel(**data)

        # Save to Supabase (optional, fails silently)
        try:
            supabase.table("contact_extractions").insert({
                "session_id": session_info["session_id"],
                "user_id": session_info["user_id"],
                "extracted_data": data,
            }).execute()
        except Exception as db_err:
            logger.warning(f"Failed to save extracted contact info: {db_err}")

        return contact

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Contact extraction failed.")
