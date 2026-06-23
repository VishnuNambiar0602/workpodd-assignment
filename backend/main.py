import os
import sys
from typing import Dict, List, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

import tools
from agent import agent_app

app = FastAPI(title="AI Refund Agent Backend")

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        # Maps customer_id to WebSocket
        self.customer_connections: Dict[int, WebSocket] = {}
        # List of admin WebSockets
        self.admin_connections: List[WebSocket] = []

    async def connect_customer(self, customer_id: int, websocket: WebSocket):
        await websocket.accept()
        self.customer_connections[customer_id] = websocket
        print(f"Customer {customer_id} connected via WebSocket.")

    def disconnect_customer(self, customer_id: int):
        if customer_id in self.customer_connections:
            del self.customer_connections[customer_id]
            print(f"Customer {customer_id} disconnected from WebSocket.")

    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.admin_connections.append(websocket)
        print("Admin connected to logs feed via WebSocket.")

    def disconnect_admin(self, websocket: WebSocket):
        if websocket in self.admin_connections:
            self.admin_connections.remove(websocket)
            print("Admin disconnected from logs feed.")

    async def send_customer_message(self, customer_id: int, message: dict):
        if customer_id in self.customer_connections:
            try:
                await self.customer_connections[customer_id].send_json(message)
            except Exception as e:
                print(f"Failed to send to customer {customer_id}: {e}")

    async def broadcast_admin_trace(self, trace_event: dict):
        disconnected = []
        for connection in self.admin_connections:
            try:
                await connection.send_json(trace_event)
            except Exception as e:
                print(f"Failed to send to admin: {e}")
                disconnected.append(connection)
                
        for conn in disconnected:
            self.disconnect_admin(conn)

manager = ConnectionManager()

# REST Endpoints

@app.get("/api/customers")
def get_customers():
    """
    Returns the basic list of all 15 customer profiles for selecting inside the UI.
    """
    try:
        customers_list = []
        with tools.get_db() as db:
            from models import Customer
            customers = db.query(Customer).order_by(Customer.id).all()
            for c in customers:
                customers_list.append({
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "tier": c.tier,
                    "past_refund_count": c.past_refund_count
                })
        return customers_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/customers/{customer_id}")
def get_customer_details(customer_id: int):
    """
    Returns full details, order histories, and past refunds for a specific customer.
    """
    try:
        profile = tools.get_customer_by_id(customer_id)
        if "error" in profile:
            raise HTTPException(status_code=404, detail=profile["error"])
        orders = tools.get_order_history(customer_id)
        refunds = tools.get_past_refunds(customer_id)
        return {
            "profile": profile,
            "orders": orders,
            "refunds": refunds
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/refunds")
def get_all_refund_claims():
    """
    Returns all refund claims (approved, denied, escalated) in the database.
    """
    try:
        with tools.get_db() as db:
            from models import Refund, Order, Customer
            # Query all refunds with order and customer names
            results = db.query(Refund, Order, Customer).join(
                Order, Refund.order_id == Order.id
            ).join(
                Customer, Order.customer_id == Customer.id
            ).order_by(Refund.created_at.desc()).all()
            
            claims = []
            for refund, order, customer in results:
                claims.append({
                    "id": refund.id,
                    "order_id": refund.order_id,
                    "customer_name": customer.name,
                    "customer_tier": customer.tier,
                    "item_name": order.item_name,
                    "category": order.category,
                    "amount": refund.amount,
                    "status": refund.status,
                    "reason": refund.reason,
                    "citation": refund.citation,
                    "created_at": str(refund.created_at)
                })
            return claims
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSockets Endpoints

@app.websocket("/ws/chat/{customer_id}")
async def websocket_chat(websocket: WebSocket, customer_id: int):
    await manager.connect_customer(customer_id, websocket)
    try:
        # Load state to keep history or initialize it
        # Note: In a production app, we would load past messages from a DB.
        # For this demo, we maintain a history list per active session.
        chat_history = []
        
        while True:
            data = await websocket.receive_json()
            user_message = data.get("text", "")
            
            if not user_message:
                continue
                
            print(f"Received from customer {customer_id}: {user_message}")
            chat_history.append(HumanMessage(content=user_message))
            
            # Send status update
            await manager.send_customer_message(customer_id, {
                "type": "status",
                "content": "Processing your request..."
            })
            
            # Streaming token callback
            tokens_streamed = False
            async def on_token(token: str):
                nonlocal tokens_streamed
                tokens_streamed = True
                await manager.send_customer_message(customer_id, {
                    "type": "token",
                    "content": token
                })
                
            initial_state = {
                "messages": chat_history,
                "customer_id": customer_id,
                "order_id": "",
                "refund_reason": "",
                "policy_chunks": [],
                "customer_context": {},
                "decision": {},
                "action_result": {},
                "trace": []
            }
            
            config = {
                "configurable": {
                    "customer_id": customer_id,
                    "on_token": on_token
                }
            }
            
            # Run the LangGraph agent in the event loop and stream node executions
            async for chunk in agent_app.astream(initial_state, config=config):
                # Broadcast trace updates to the admin WebSocket as they complete
                for node_name, state_updates in chunk.items():
                    if "trace" in state_updates:
                        for trace_event in state_updates["trace"]:
                            # Send trace log to all admins
                            await manager.broadcast_admin_trace({
                                "type": "trace",
                                "customer_id": customer_id,
                                "customer_name": tools.get_customer_by_id(customer_id).get("name", "Unknown"),
                                "data": trace_event
                            })
                            
                    # Update message history if new AIMessage is appended
                    if "messages" in state_updates:
                        for msg in state_updates["messages"]:
                            chat_history.append(msg)
                            
            # Send the fallback message if no tokens were streamed (e.g. LLM call failed and we returned fallback text)
            if not tokens_streamed and chat_history and chat_history[-1].type == "ai":
                await manager.send_customer_message(customer_id, {
                    "type": "token",
                    "content": chat_history[-1].content
                })
                
            # End response stream
            await manager.send_customer_message(customer_id, {
                "type": "end_response"
            })
            
    except WebSocketDisconnect:
        manager.disconnect_customer(customer_id)
    except Exception as e:
        print(f"WebSocket error for customer {customer_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "content": f"An error occurred: {str(e)}"})
        except Exception:
            pass
        manager.disconnect_customer(customer_id)

@app.websocket("/ws/admin/logs")
async def websocket_admin_logs(websocket: WebSocket):
    await manager.connect_admin(websocket)
    try:
        while True:
            # Admins don't need to send messages, just keep the socket open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_admin(websocket)
    except Exception as e:
        print(f"Admin socket error: {e}")
        manager.disconnect_admin(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
