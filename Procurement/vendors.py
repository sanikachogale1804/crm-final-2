from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class VendorCreate(BaseModel):
    name: str
    email: str

@router.post("/vendors")
def create_vendor(data: VendorCreate):
    return {
        "success": True,
        "message": "Vendor created successfully",
        "data": data
    }
