import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

from database import create_document
from database import db
from schemas import Lead, Product
from bson import ObjectId

app = FastAPI(title="Christmas 3D Shop API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utils
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc["id"] = str(doc.get("_id"))
    doc.pop("_id", None)
    return doc

@app.get("/")
def read_root():
    return {"message": "Christmas 3D Shop Backend is running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# ----- Leads endpoint for contact capture -----
class LeadIn(BaseModel):
    name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    message: Optional[str] = None

@app.post("/api/leads")
def create_lead(lead: LeadIn):
    try:
        lead_doc = Lead(**lead.model_dump())
        inserted_id = create_document("lead", lead_doc)
        return {"status": "ok", "id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----- Products CRUD -----
class ProductIn(BaseModel):
    title: str = Field(...)
    description: Optional[str] = Field(None)
    price: float = Field(..., ge=0)
    category: str = Field("Geral")
    in_stock: bool = Field(True)

class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    in_stock: Optional[bool] = None

@app.get("/api/products")
def list_products() -> List[dict]:
    try:
        docs = list(db["product"].find({}).sort("created_at", -1)) if db is not None else []
        return [serialize_doc(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products")
def create_product(payload: ProductIn):
    try:
        prod_doc = Product(**payload.model_dump())
        inserted_id = create_document("product", prod_doc)
        return {"status": "ok", "id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/products/{product_id}")
def update_product(product_id: str, payload: ProductUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        oid = PyObjectId.validate(product_id)
        data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")
        data["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        res = db["product"].update_one({"_id": oid}, {"$set": data})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        doc = db["product"].find_one({"_id": oid})
        return serialize_doc(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        oid = PyObjectId.validate(product_id)
        res = db["product"].delete_one({"_id": oid})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
