import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Customer(Base):
    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    tier = Column(String(50), default='standard')  # 'standard' or 'premium'
    signup_date = Column(Date, default=datetime.date.today)
    past_refund_count = Column(Integer, default=0)

    orders = relationship("Order", back_populates="customer")

class Order(Base):
    __tablename__ = 'orders'

    id = Column(String(50), primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    item_name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)  # 'electronics', 'apparel', 'digital', 'other'
    price = Column(Float, nullable=False)
    order_date = Column(Date, nullable=False)
    delivery_date = Column(Date, nullable=True)
    status = Column(String(50), nullable=False)  # 'delivered', 'processing', 'shipped', 'cancelled'

    customer = relationship("Customer", back_populates="orders")
    refunds = relationship("Refund", back_populates="order")

class Refund(Base):
    __tablename__ = 'refunds'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(50), ForeignKey('orders.id'), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False)  # 'approved', 'denied', 'escalated'
    reason = Column(Text, nullable=True)
    citation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    order = relationship("Order", back_populates="refunds")

class PolicyChunk(Base):
    __tablename__ = 'policy_chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    section = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384))  # dimension of all-MiniLM-L6-v2 is 384


