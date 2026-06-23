import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Import models
from models import Customer, Order, Refund, PolicyChunk

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/refund_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Cache embedding model to avoid reloading on every function call
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_customer_by_id(customer_id: int) -> dict:
    """
    Retrieves customer details by customer ID.
    """
    with get_db() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"error": f"Customer with ID {customer_id} not found."}
        return {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "tier": customer.tier,
            "signup_date": str(customer.signup_date),
            "past_refund_count": customer.past_refund_count
        }

def get_order_history(customer_id: int) -> list[dict]:
    """
    Retrieves all past orders for a customer by their ID.
    """
    with get_db() as db:
        orders = db.query(Order).filter(Order.customer_id == customer_id).all()
        return [
            {
                "id": o.id,
                "item_name": o.item_name,
                "category": o.category,
                "price": o.price,
                "order_date": str(o.order_date),
                "delivery_date": str(o.delivery_date) if o.delivery_date else None,
                "status": o.status
            }
            for o in orders
        ]

def get_past_refunds(customer_id: int) -> list[dict]:
    """
    Retrieves all past refund requests (approved, denied, escalated) for a customer.
    """
    with get_db() as db:
        refunds = db.query(Refund).join(Order).filter(Order.customer_id == customer_id).all()
        return [
            {
                "id": r.id,
                "order_id": r.order_id,
                "amount": r.amount,
                "status": r.status,
                "reason": r.reason,
                "citation": r.citation,
                "created_at": str(r.created_at)
            }
            for r in refunds
        ]

def search_refund_policy(query: str, limit: int = 3) -> list[dict]:
    """
    Queries the vector database for policy rules matching the semantic meaning of the query.
    """
    model = get_embedding_model()
    query_embedding = model.encode(query).tolist()
    
    with get_db() as db:
        # Perform similarity search using pgvector's cosine_distance operator
        results = db.query(PolicyChunk).order_by(
            PolicyChunk.embedding.cosine_distance(query_embedding)
        ).limit(limit).all()
        
        return [
            {
                "section": r.section,
                "content": r.content
            }
            for r in results
        ]

def process_refund(order_id: str, amount: float, reason: str, citation: str) -> dict:
    """
    Processes a refund approval: writes the approved refund to the database
    and increments the customer's past refund count.
    """
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": f"Order with ID {order_id} not found."}
        
        # Check if refund already exists for this order
        existing = db.query(Refund).filter(Refund.order_id == order_id, Refund.status == 'approved').first()
        if existing:
            return {"error": f"Refund has already been approved for order {order_id}."}
            
        # Create refund record
        refund = Refund(
            order_id=order_id,
            amount=amount,
            status="approved",
            reason=reason,
            citation=citation
        )
        db.add(refund)
        
        # Increment customer's past refund count
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        if customer:
            customer.past_refund_count += 1
            
        db.commit()
        return {
            "success": True,
            "refund_id": refund.id,
            "status": "approved",
            "order_id": order_id,
            "amount": amount
        }

def deny_refund(order_id: str, reason: str, citation: str) -> dict:
    """
    Denies a refund request: writes the denied status and reason to the database.
    """
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": f"Order with ID {order_id} not found."}
            
        refund = Refund(
            order_id=order_id,
            amount=0.0,
            status="denied",
            reason=reason,
            citation=citation
        )
        db.add(refund)
        db.commit()
        
        return {
            "success": True,
            "refund_id": refund.id,
            "status": "denied",
            "order_id": order_id
        }

def escalate_refund(order_id: str, amount: float, reason: str, citation: str) -> dict:
    """
    Escalates a refund request to a human administrator for review.
    """
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": f"Order with ID {order_id} not found."}
            
        refund = Refund(
            order_id=order_id,
            amount=amount,
            status="escalated",
            reason=reason,
            citation=citation
        )
        db.add(refund)
        db.commit()
        
        return {
            "success": True,
            "refund_id": refund.id,
            "status": "escalated",
            "order_id": order_id,
            "amount": amount
        }
