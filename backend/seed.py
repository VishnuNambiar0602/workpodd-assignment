import os
import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/refund_db")

# Import models
from models import Base, Customer, Order, Refund, PolicyChunk

def parse_policy(filepath):
    """
    Parses refund_policy.md into logical sections by splitting on markdown headers (##).
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Policy file not found at {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    sections = []
    # Split content by markdown sections starting with '## '
    parts = content.split("## ")
    
    # The first part is usually the title '# E-Commerce Store Refund Policy'
    title = parts[0].strip()
    
    for part in parts[1:]:
        lines = part.strip().split("\n")
        section_title = lines[0].strip()
        section_content = "\n".join(lines[1:]).strip()
        
        # Combine title and content for embedding/context preservation
        full_text = f"Section: {section_title}\n\n{section_content}"
        sections.append({
            "section": section_title,
            "content": full_text
        })
        
    return sections

def seed_database():
    print("Connecting to database...")
    engine = create_engine(DATABASE_URL)
    
    # Enable vector extension in Postgres
    with engine.connect() as conn:
        print("Enabling pgvector extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
        
    # Recreate tables
    print("Dropping and recreating tables...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("Seeding customer profiles...")
    customers = [
        Customer(id=1, name="Alice Smith", email="alice@example.com", tier="standard", signup_date=datetime.date(2025, 1, 15), past_refund_count=0),
        Customer(id=2, name="Bob Jones", email="bob@example.com", tier="premium", signup_date=datetime.date(2024, 5, 10), past_refund_count=1),
        Customer(id=3, name="Charlie Brown", email="charlie@example.com", tier="standard", signup_date=datetime.date(2023, 11, 20), past_refund_count=3),
        Customer(id=4, name="Diana Prince", email="diana@example.com", tier="premium", signup_date=datetime.date(2025, 3, 1), past_refund_count=0),
        Customer(id=5, name="Evan Wright", email="evan@example.com", tier="standard", signup_date=datetime.date(2025, 9, 12), past_refund_count=2),
        Customer(id=6, name="Fiona Gallagher", email="fiona@example.com", tier="standard", signup_date=datetime.date(2024, 8, 5), past_refund_count=4),
        Customer(id=7, name="George Clooney", email="george@example.com", tier="premium", signup_date=datetime.date(2025, 12, 1), past_refund_count=0),
        Customer(id=8, name="Hannah Abbott", email="hannah@example.com", tier="standard", signup_date=datetime.date(2025, 2, 18), past_refund_count=1),
        Customer(id=9, name="Ian Malcolm", email="ian@example.com", tier="premium", signup_date=datetime.date(2023, 4, 15), past_refund_count=2),
        Customer(id=10, name="Julia Roberts", email="julia@example.com", tier="standard", signup_date=datetime.date(2024, 10, 10), past_refund_count=0),
        Customer(id=11, name="Kevin Bacon", email="kevin@example.com", tier="standard", signup_date=datetime.date(2025, 7, 22), past_refund_count=0),
        Customer(id=12, name="Laura Croft", email="laura@example.com", tier="premium", signup_date=datetime.date(2024, 2, 14), past_refund_count=0),
        Customer(id=13, name="Michael Scott", email="michael@example.com", tier="standard", signup_date=datetime.date(2025, 5, 5), past_refund_count=5),
        Customer(id=14, name="Nancy Drew", email="nancy@example.com", tier="premium", signup_date=datetime.date(2025, 11, 11), past_refund_count=1),
        Customer(id=15, name="Oliver Twist", email="oliver@example.com", tier="standard", signup_date=datetime.date(2026, 1, 1), past_refund_count=0)
    ]
    session.add_all(customers)
    
    print("Seeding order history...")
    orders = [
        # Alice Smith
        Order(id="ORD-001", customer_id=1, item_name="Premium Headphones", category="electronics", price=120.0, order_date=datetime.date(2026, 6, 10), delivery_date=datetime.date(2026, 6, 12), status="delivered"),
        Order(id="ORD-002", customer_id=1, item_name="Wireless Mouse", category="electronics", price=25.0, order_date=datetime.date(2026, 6, 15), delivery_date=datetime.date(2026, 6, 16), status="delivered"),
        
        # Bob Jones
        Order(id="ORD-003", customer_id=2, item_name="Winter Jacket", category="apparel", price=150.0, order_date=datetime.date(2026, 5, 20), delivery_date=datetime.date(2026, 5, 22), status="delivered"),
        Order(id="ORD-004", customer_id=2, item_name="Slim Fit Jeans", category="apparel", price=80.0, order_date=datetime.date(2026, 4, 1), delivery_date=datetime.date(2026, 4, 3), status="delivered"),
        
        # Charlie Brown
        Order(id="ORD-005", customer_id=3, item_name="Bluetooth Earbuds", category="electronics", price=99.0, order_date=datetime.date(2026, 6, 10), delivery_date=datetime.date(2026, 6, 12), status="delivered"),
        
        # Diana Prince
        Order(id="ORD-006", customer_id=4, item_name="Mechanical Keyboard", category="electronics", price=120.0, order_date=datetime.date(2026, 5, 10), delivery_date=datetime.date(2026, 5, 12), status="delivered"),
        Order(id="ORD-007", customer_id=4, item_name="Smartwatch", category="electronics", price=180.0, order_date=datetime.date(2026, 6, 14), delivery_date=datetime.date(2026, 6, 15), status="delivered"),
        
        # Evan Wright
        Order(id="ORD-008", customer_id=5, item_name="Cotton T-Shirt", category="apparel", price=30.0, order_date=datetime.date(2026, 6, 5), delivery_date=datetime.date(2026, 6, 7), status="delivered"),
        Order(id="ORD-009", customer_id=5, item_name="Office Software Suite", category="digital", price=50.0, order_date=datetime.date(2026, 6, 15), delivery_date=None, status="delivered"),
        
        # Fiona Gallagher
        Order(id="ORD-010", customer_id=6, item_name="Summer Dress", category="apparel", price=90.0, order_date=datetime.date(2026, 6, 10), delivery_date=datetime.date(2026, 6, 12), status="delivered"),
        
        # George Clooney
        Order(id="ORD-011", customer_id=7, item_name="Sci-Fi E-book", category="digital", price=15.0, order_date=datetime.date(2026, 6, 17), delivery_date=None, status="delivered"),
        Order(id="ORD-012", customer_id=7, item_name="Android Tablet", category="electronics", price=300.0, order_date=datetime.date(2026, 6, 12), delivery_date=datetime.date(2026, 6, 14), status="delivered"),
        
        # Hannah Abbott
        Order(id="ORD-013", customer_id=8, item_name="Designer Jacket (FINAL-SALE)", category="apparel", price=45.0, order_date=datetime.date(2026, 6, 8), delivery_date=datetime.date(2026, 6, 10), status="delivered"),
        
        # Ian Malcolm
        Order(id="ORD-014", customer_id=9, item_name="Premium Leather Shoes", category="apparel", price=220.0, order_date=datetime.date(2026, 6, 5), delivery_date=datetime.date(2026, 6, 7), status="delivered"),
        
        # Julia Roberts
        Order(id="ORD-015", customer_id=10, item_name="Espresso Maker", category="electronics", price=60.0, order_date=datetime.date(2026, 6, 1), delivery_date=datetime.date(2026, 6, 3), status="delivered"),
        
        # Kevin Bacon
        Order(id="ORD-016", customer_id=11, item_name="Holiday Sale Hoodie", category="apparel", price=50.0, order_date=datetime.date(2026, 6, 2), delivery_date=datetime.date(2026, 6, 5), status="delivered"),
        
        # Laura Croft
        Order(id="ORD-017", customer_id=12, item_name="Next-Gen Gaming Console", category="electronics", price=499.0, order_date=datetime.date(2026, 6, 12), delivery_date=datetime.date(2026, 6, 14), status="delivered"),
        
        # Michael Scott
        Order(id="ORD-018", customer_id=13, item_name="Heavy Duty Paper Shredder", category="electronics", price=85.0, order_date=datetime.date(2026, 6, 15), delivery_date=datetime.date(2026, 6, 16), status="delivered"),
        
        # Nancy Drew
        Order(id="ORD-019", customer_id=14, item_name="Vintage Magnifying Glass", category="apparel", price=35.0, order_date=datetime.date(2026, 6, 11), delivery_date=datetime.date(2026, 6, 13), status="delivered"),
        
        # Oliver Twist
        Order(id="ORD-020", customer_id=15, item_name="Ceramic Soup Bowl", category="apparel", price=10.0, order_date=datetime.date(2026, 6, 15), delivery_date=datetime.date(2026, 6, 16), status="delivered")
    ]
    session.add_all(orders)
    
    print("Generating embeddings for policy document...")
    # Initialize the local embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    policy_path = os.path.join(os.path.dirname(__file__), "refund_policy.md")
    policy_sections = parse_policy(policy_path)
    
    policy_chunks = []
    for section in policy_sections:
        print(f"Embedding section: {section['section']}")
        embedding = model.encode(section['content']).tolist()
        policy_chunk = PolicyChunk(
            section=section['section'],
            content=section['content'],
            embedding=embedding
        )
        policy_chunks.append(policy_chunk)
        
    session.add_all(policy_chunks)
    
    session.commit()
    print("Database seeding completed successfully!")
    
if __name__ == "__main__":
    seed_database()
