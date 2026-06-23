import os
import asyncio
import operator
import re
import datetime
from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks import AsyncCallbackHandler
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

# Import database tool functions
import tools

load_dotenv()

def local_rule_based_decision(state: Dict[str, Any]) -> Dict[str, Any]:
    customer_context = state.get("customer_context", {})
    profile = customer_context.get("profile", {})
    orders = customer_context.get("orders", [])
    past_refunds = customer_context.get("past_refunds", [])
    
    order_id = state.get("order_id", "").upper().strip()
    refund_reason = state.get("refund_reason", "")
    
    # Check if greeting or missing details
    if not order_id:
        return {
            "action": "chat",
            "amount": 0.0,
            "reason": "Missing order details or simple greeting.",
            "citation": "Make your decision: 'approve', 'deny', 'escalate', or 'chat' (if missing details or greeting).",
            "explanation": "Hello! I can help you with your refund requests. Please tell me your order ID (e.g. ORD-001) and the reason you'd like a refund."
        }
        
    # Find the target order
    target_order = None
    for o in orders:
        if o["id"].upper().strip() == order_id:
            target_order = o
            break
            
    if not target_order:
        return {
            "action": "chat",
            "amount": 0.0,
            "reason": f"Order {order_id} not found for this customer.",
            "citation": "Make your decision: 'approve', 'deny', 'escalate', or 'chat' (if missing details or greeting).",
            "explanation": f"I'm sorry, I couldn't find any order with ID {order_id} in your order history. Please check the order ID and try again."
        }
        
    # Check rule 1: Abuse Escalation (past_refund_count >= 3)
    past_refund_count = profile.get("past_refund_count", 0)
    if past_refund_count >= 3:
        return {
            "action": "escalate",
            "amount": target_order["price"],
            "reason": f"Abuse Risk: Customer has {past_refund_count} past refunds (limit is < 3).",
            "citation": "A customer is flagged as an ABUSE risk if profile past_refund_count >= 3. Their request MUST be escalated.",
            "explanation": f"Your refund request for order {order_id} has been escalated to a representative for manual review because your account has reached our automated refund review limit."
        }
        
    # Check rule 2: Calendar year 2026 refund cap of $200
    # Let's count all refunds already approved in 2026
    refunds_2026_sum = 0.0
    for r in past_refunds:
        if r["status"] == "approved" and "2026" in str(r.get("created_at", "")):
            refunds_2026_sum += float(r.get("amount", 0.0))
            
    # Calculate days since delivery
    today = datetime.date(2026, 6, 18)
    
    delivery_date_str = target_order.get("delivery_date")
    order_date_str = target_order.get("order_date")
    
    delivery_date = None
    if delivery_date_str and delivery_date_str != "None":
        try:
            delivery_date = datetime.datetime.strptime(delivery_date_str.split(" ")[0], "%Y-%m-%d").date()
        except Exception:
            pass
            
    order_date = None
    if order_date_str and order_date_str != "None":
        try:
            order_date = datetime.datetime.strptime(order_date_str.split(" ")[0], "%Y-%m-%d").date()
        except Exception:
            pass
            
    ref_date = delivery_date or order_date or today
    days_since_ref = (today - ref_date).days
    
    category = target_order.get("category", "").lower().strip()
    item_title = target_order.get("item_name", "")
    price = float(target_order.get("price", 0.0))
    tier = profile.get("tier", "standard").lower().strip()
    
    # Evaluate Category Refund Windows
    is_defective = any(w in refund_reason.lower() for w in ["defect", "broken", "stop working", "not working", "damaged", "faulty", "issue", "speaker"])
    
    if category == "electronics":
        if days_since_ref > 15:
            return {
                "action": "deny",
                "amount": 0.0,
                "reason": f"Electronics return window exceeded ({days_since_ref} days since delivery, limit 15 days).",
                "citation": "Electronics: 15 days from delivery date. Needs proof of defect if >7 days after delivery.",
                "explanation": f"I'm sorry, but we cannot approve a refund for order {order_id} because the 15-day return window for electronics has expired ({days_since_ref} days have passed since delivery)."
            }
        elif days_since_ref > 7 and not is_defective:
            return {
                "action": "escalate",
                "amount": price,
                "reason": f"Electronics return after 7 days ({days_since_ref} days) requires defect validation.",
                "citation": "Electronics: 15 days from delivery date. Needs proof of defect if >7 days after delivery.",
                "explanation": f"Your refund request for order {order_id} has been escalated to our team because returns for electronic items after 7 days require verification of the technical issue you reported."
            }
            
    elif category == "apparel":
        if "final-sale" in item_title.lower() or "final sale" in item_title.lower():
            return {
                "action": "deny",
                "amount": 0.0,
                "reason": "Apparel item is marked Final Sale.",
                "citation": "Apparel: 30 days from delivery date. Final Sale items (\"FINAL-SALE\" in title) are non-refundable.",
                "explanation": f"I'm sorry, but your refund request for order {order_id} cannot be approved because the item '{item_title}' was purchased as a Final Sale, which is non-refundable under our store policy."
            }
        if days_since_ref > 30:
            return {
                "action": "deny",
                "amount": 0.0,
                "reason": f"Apparel return window exceeded ({days_since_ref} days since delivery, limit 30 days).",
                "citation": "Apparel: 30 days from delivery date.",
                "explanation": f"I'm sorry, but your refund request for order {order_id} cannot be approved because it has been {days_since_ref} days since delivery, which exceeds our 30-day apparel return policy."
            }
            
    elif category == "digital":
        days_since_purchase = (today - (order_date or today)).days
        if days_since_purchase <= 7 and is_defective:
            pass
        else:
            reason_msg = "Digital goods are non-refundable once delivered"
            if days_since_purchase > 7:
                reason_msg += f" (purchased {days_since_purchase} days ago, limit for defect is 7 days)"
            else:
                reason_msg += " (no technical defect reported)"
            return {
                "action": "deny",
                "amount": 0.0,
                "reason": reason_msg,
                "citation": "Digital: 0 days (non-refundable once delivered) EXCEPT technical defect within 7 days of purchase.",
                "explanation": f"I'm sorry, but digital items are non-refundable once delivered. Under our policy, digital items are only eligible for a refund if a technical defect is reported within 7 days of purchase."
            }
            
    else:
        if days_since_ref > 30:
            return {
                "action": "deny",
                "amount": 0.0,
                "reason": f"Return window exceeded ({days_since_ref} days).",
                "citation": "Make your decision: 'approve', 'deny', 'escalate', or 'chat'.",
                "explanation": f"I'm sorry, but we cannot approve a refund for order {order_id} as the return window has expired."
            }

    # Restocking Fees Calculation
    restocking_fee_pct = 0.0
    fee_applied_reason = ""
    is_holiday_sale = "holiday sale" in item_title.lower()
    
    if is_holiday_sale:
        if tier == "premium":
            restocking_fee_pct = 0.20
            fee_applied_reason = "Holiday Sale item 20% restocking fee for Premium tier"
        else:
            restocking_fee_pct = 0.50
            fee_applied_reason = "Holiday Sale item 50% restocking fee for Standard tier"
    elif category in ["electronics", "apparel"]:
        if tier == "standard":
            if is_defective:
                restocking_fee_pct = 0.0
                fee_applied_reason = "Standard tier restocking fee waived due to reported defect"
            else:
                restocking_fee_pct = 0.10
                fee_applied_reason = "Standard tier 10% restocking fee on physical returns"
        else:
            restocking_fee_pct = 0.0
            fee_applied_reason = "Premium tier is exempt from restocking fees"
            
    refund_amount = price * (1.0 - restocking_fee_pct)
    
    # Check limit check
    if refunds_2026_sum + refund_amount > 200.0:
        return {
            "action": "escalate",
            "amount": refund_amount,
            "reason": f"Calendar year limit exceeded. Prior refunds: ${refunds_2026_sum:.2f}, current request: ${refund_amount:.2f}.",
            "citation": "The total amount refunded in the current calendar year (2026) cannot exceed $200. If the refund pushes them over $200, the request MUST be escalated.",
            "explanation": f"Your refund request for order {order_id} has been escalated for review because the refund amount of ${refund_amount:.2f} would push your account past our annual refund cap of $200.00."
        }
        
    explanation = f"Your refund request for order {order_id} has been approved."
    if restocking_fee_pct > 0.0:
        explanation += f" A restocking fee of {int(restocking_fee_pct*100)}% (${price * restocking_fee_pct:.2f}) was applied as per policy ({fee_applied_reason}). Your net refund is ${refund_amount:.2f}."
    else:
        explanation += f" You will receive a full refund of ${refund_amount:.2f} (restocking fee waived/exempt: {fee_applied_reason})."
        
    return {
        "action": "approve",
        "amount": refund_amount,
        "reason": f"Approved refund of ${refund_amount:.2f} under {category} guidelines. Restocking fee: {restocking_fee_pct*100}% ({fee_applied_reason}).",
        "citation": f"Category rule for {category} & fee rule for {tier} tier.",
        "explanation": explanation
    }


# Define the LangGraph State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    customer_id: int
    order_id: str
    refund_reason: str
    policy_chunks: List[Dict[str, Any]]
    customer_context: Dict[str, Any]
    decision: Dict[str, Any]
    action_result: Dict[str, Any]
    trace: Annotated[List[Dict[str, Any]], operator.add]

# Pydantic Schemas for Structured LLM Outputs
class IntakeExtraction(BaseModel):
    order_id: str = Field(default="", description="The order ID mentioned by the customer, e.g. ORD-001. Empty string if none.")
    refund_reason: str = Field(default="", description="The reason the customer is requesting a refund. Empty string if none.")

class SearchQueryGeneration(BaseModel):
    search_query: str = Field(description="A search query to query the store's refund policy database.")

class RefundDecision(BaseModel):
    action: str = Field(description="Action to perform: 'approve', 'deny', 'escalate', or 'chat' (if general discussion, greetings, or missing order details).")
    amount: float = Field(description="Refund amount. Set to 0 if denied or chat. Set to correct order price (considering category, fees, caps) if approved/escalated.")
    reason: str = Field(description="The primary reason justifying this action based on policy.")
    citation: str = Field(description="A direct quote or section heading from the retrieved policy chunks that justifies the decision.")
    explanation: str = Field(description="Polite, clear explanation for the customer detailing why this decision was made and any fees applied.")

# Custom Callback to stream tokens over WebSockets
class TokenStreamingCallback(AsyncCallbackHandler):
    def __init__(self, token_cb):
        self.token_cb = token_cb

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        if self.token_cb:
            if asyncio.iscoroutinefunction(self.token_cb):
                await self.token_cb(token)
            else:
                self.token_cb(token)

# Initialize LLM
def get_llm():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=api_key, temperature=0)

# LangGraph Node Functions (Async)

async def intake_node(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    print("[Node: intake]")
    customer_id = 1
    if config and "configurable" in config and "customer_id" in config["configurable"]:
        customer_id = config["configurable"]["customer_id"]
        
    last_message = state["messages"][-1].content if state["messages"] else ""
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(IntakeExtraction)
    
    try:
        extraction = await structured_llm.ainvoke([
            SystemMessage(content="Extract the order ID (e.g. ORD-001) and customer refund reason from the latest message. If there is a history, use it to resolve context."),
            HumanMessage(content=last_message)
        ])
        order_id = extraction.order_id
        refund_reason = extraction.refund_reason
    except Exception as e:
        print(f"Intake extraction error: {e}")
        # Fallback to local extraction regex/heuristic
        match = re.search(r'(ORD-\d+)', last_message, re.IGNORECASE)
        order_id = match.group(1).upper() if match else ""
        refund_reason = last_message if ("refund" in last_message.lower() or "return" in last_message.lower() or "broken" in last_message.lower() or "defect" in last_message.lower()) else ""

    trace_event = {
        "node": "intake",
        "tool_called": "llm_intake_extraction",
        "tool_input": f"Message: '{last_message}'",
        "tool_output": f"Extracted: order_id='{order_id}', reason='{refund_reason}'",
        "reasoning": "Parsing user message for refund intent, extracting order IDs and reasons."
    }
    
    return {
        "customer_id": customer_id,
        "order_id": order_id if order_id else state.get("order_id", ""),
        "refund_reason": refund_reason if refund_reason else state.get("refund_reason", ""),
        "trace": [trace_event]
    }

async def fetch_customer_context_node(state: AgentState) -> Dict[str, Any]:
    print("[Node: fetch_customer_context]")
    customer_id = state.get("customer_id")
    if not customer_id:
        return {"trace": [{"node": "fetch_customer_context", "tool_called": "None", "tool_input": "None", "tool_output": "No customer_id found", "reasoning": "Skipping lookup."}]}
        
    print(f"Fetching context for customer {customer_id}")
    # Wrap database synchronous calls in executor to avoid blocking the async event loop
    loop = asyncio.get_running_loop()
    profile = await loop.run_in_executor(None, tools.get_customer_by_id, customer_id)
    orders = await loop.run_in_executor(None, tools.get_order_history, customer_id)
    past_refunds = await loop.run_in_executor(None, tools.get_past_refunds, customer_id)
    
    context = {
        "profile": profile,
        "orders": orders,
        "past_refunds": past_refunds
    }
    
    trace_event = {
        "node": "fetch_customer_context",
        "tool_called": "get_customer_by_id, get_order_history, get_past_refunds",
        "tool_input": f"customer_id={customer_id}",
        "tool_output": f"Profile loaded. Found {len(orders)} orders and {len(past_refunds)} past refunds.",
        "reasoning": f"Loading CRM database entries for customer {customer_id} to verify eligibility and policy triggers."
    }
    
    return {
        "customer_context": context,
        "trace": [trace_event]
    }

async def retrieve_policy_node(state: AgentState) -> Dict[str, Any]:
    print("[Node: retrieve_policy]")
    order_id = state.get("order_id")
    refund_reason = state.get("refund_reason")
    last_message = state["messages"][-1].content if state["messages"] else ""
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(SearchQueryGeneration)
    
    query = f"refund policy limits categories windows"
    try:
        query_res = await structured_llm.ainvoke([
            SystemMessage(content="Generate a single concise search term to query the database refund policy for the user's issue."),
            HumanMessage(content=f"Message: {last_message}\nOrder ID: {order_id}\nReason: {refund_reason}")
        ])
        query = query_res.search_query
    except Exception as e:
        print(f"Query generation error: {e}")
        query = "refund policy limits categories windows"
        
    print(f"Policy search query: {query}")
    loop = asyncio.get_running_loop()
    policy_results = await loop.run_in_executor(None, tools.search_refund_policy, query, 3)
    
    trace_event = {
        "node": "retrieve_policy",
        "tool_called": "search_refund_policy",
        "tool_input": f"query='{query}'",
        "tool_output": f"Retrieved {len(policy_results)} relevant policy sections.",
        "reasoning": f"Querying the vector store (pgvector) to find policy text relating to the user's request."
    }
    
    return {
        "policy_chunks": policy_results,
        "trace": [trace_event]
    }

async def reason_and_decide_node(state: AgentState) -> Dict[str, Any]:
    print("[Node: reason_and_decide]")
    llm = get_llm()
    structured_llm = llm.with_structured_output(RefundDecision)
    
    customer_context = state.get("customer_context", {})
    profile = customer_context.get("profile", {})
    orders = customer_context.get("orders", [])
    past_refunds = customer_context.get("past_refunds", [])
    
    policy_text = ""
    for idx, chunk in enumerate(state.get("policy_chunks", [])):
        policy_text += f"\n[Chunk {idx+1}] Section: {chunk['section']}\n{chunk['content']}\n"
        
    order_id = state.get("order_id")
    refund_reason = state.get("refund_reason")
    
    target_order = None
    if order_id:
        for o in orders:
            if o["id"] == order_id:
                target_order = o
                break
                
    analysis_input = f"""
    Current Date: 2026-06-18 (USE THIS AS TODAY'S DATE)
    
    Customer Profile:
    - ID: {profile.get("id")}
    - Name: {profile.get("name")}
    - Email: {profile.get("email")}
    - Tier: {profile.get("tier")}
    - Past Refund Count: {profile.get("past_refund_count")}
    
    Target Order Details:
    {target_order if target_order else f"No matching order found for ID '{order_id}'"}
    
    All Customer Orders:
    {orders}
    
    Past Refunds (Current Status):
    {past_refunds}
    
    Customer Request & Reason:
    - Requested Order: {order_id}
    - Reported Reason: {refund_reason}
    
    Retrieved Refund Policies (Vector Search):
    {policy_text}
    """
    
    system_prompt = """
    You are the core decider engine in a strict automated refund system.
    Evaluate the customer request against the database profile and the retrieved policies.
    
    STRICT RULES:
    1. A customer is flagged as an ABUSE risk if profile past_refund_count >= 3. Their request MUST be escalated.
    2. The total amount refunded in the current calendar year (2026) cannot exceed $200. If the refund pushes them over $200, the request MUST be escalated.
    3. Category Refund Windows:
       - Electronics: 15 days from delivery date. Needs proof of defect if >7 days after delivery.
       - Apparel: 30 days from delivery date. Final Sale items ("FINAL-SALE" in title) are non-refundable.
       - Digital: 0 days (non-refundable once delivered) EXCEPT technical defect within 7 days of purchase.
    4. Fees:
       - Standard tier customers are charged a 10% restocking fee on physical returns (Electronics, Apparel) unless the item is verified as defective.
       - Premium tier customers are exempt from restocking fees.
       - Holiday Sale items (e.g. "Holiday Sale" in title) have 50% restocking fee for standard, 20% for premium.
    
    Make your decision: 'approve', 'deny', 'escalate', or 'chat' (if missing details or greeting).
    Provide the exact citation from the policy and a clear explanation of calculations.
    """
    
    try:
        decision_res = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=analysis_input)
        ])
        decision = decision_res.model_dump()
    except Exception as e:
        print(f"Decision processing error: {e}")
        # Run local rule-based compliance decision
        decision = local_rule_based_decision(state)
        
    print(f"Agent Decision: {decision}")
    
    trace_event = {
        "node": "reason_and_decide",
        "tool_called": "llm_decision_engine",
        "tool_input": f"Order: {order_id}, Reason: {refund_reason}",
        "tool_output": f"Action={decision['action']}, Amount=${decision['amount']}, Reason={decision['reason']}",
        "reasoning": f"Evaluated rules. Abuse check: count={profile.get('past_refund_count')}. Limits check: refunding=${decision['amount']}. Policy matching: {decision['reason']}"
    }
    
    return {
        "decision": decision,
        "trace": [trace_event]
    }

async def execute_action_node(state: AgentState) -> Dict[str, Any]:
    print("[Node: execute_action]")
    decision = state.get("decision", {})
    action = decision.get("action")
    order_id = state.get("order_id")
    amount = decision.get("amount", 0.0)
    reason = decision.get("reason", "")
    citation = decision.get("citation", "")
    
    result = {"status": "skipped", "message": "No database write required."}
    loop = asyncio.get_running_loop()
    
    if action == "approve" and order_id:
        print(f"Writing approval to database for order {order_id}...")
        result = await loop.run_in_executor(None, tools.process_refund, order_id, amount, reason, citation)
    elif action == "deny" and order_id:
        print(f"Writing denial to database for order {order_id}...")
        result = await loop.run_in_executor(None, tools.deny_refund, order_id, reason, citation)
    elif action == "escalate" and order_id:
        print(f"Writing escalation to database for order {order_id}...")
        result = await loop.run_in_executor(None, tools.escalate_refund, order_id, amount, reason, citation)
        
    trace_event = {
        "node": "execute_action",
        "tool_called": f"{action}_refund" if action in ["approve", "deny", "escalate"] else "None",
        "tool_input": f"order_id={order_id}, amount={amount}",
        "tool_output": f"Result: {result}",
        "reasoning": f"Executing database transaction to write state of refund request for {order_id}."
    }
    
    return {
        "action_result": result,
        "trace": [trace_event]
    }

async def respond_node(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    print("[Node: respond]")
    decision = state.get("decision", {})
    explanation = decision.get("explanation", "How can I help you today?")
    
    # Retrieve WebSocket streaming callback if provided
    on_token = None
    if config and "configurable" in config:
        on_token = config["configurable"].get("on_token")
        
    system_prompt = "You are a customer service chatbot. Convey the decision and explanation politely to the customer. Maintain a friendly but policy-compliant tone."
    user_context = f"Decision: {decision.get('action')}, Amount: {decision.get('amount')}, Details: {explanation}"
    
    # Instantiate LLM with streaming callbacks if callback is available
    if on_token:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            streaming=True,
            callbacks=[TokenStreamingCallback(on_token)],
            temperature=0,
            google_api_key=api_key
        )
    else:
        llm = get_llm()
        
    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_context)
        ])
        response_text = response.content
    except Exception as e:
        print(f"Respond synthesis error: {e}")
        response_text = explanation
        
    trace_event = {
        "node": "respond",
        "tool_called": "llm_response_synthesis",
        "tool_input": f"Explanation: {explanation}",
        "tool_output": f"Response: {response_text[:60]}...",
        "reasoning": "Formulating natural language response based on system decision."
    }
    
    return {
        "messages": [AIMessage(content=response_text)],
        "trace": [trace_event]
    }

# Conditional routing edge
def route_after_decide(state: AgentState):
    decision = state.get("decision", {})
    action = decision.get("action")
    if action in ["approve", "deny", "escalate"]:
        return "execute_action"
    return "respond"

# Build Graph Workflow
workflow = StateGraph(AgentState)

workflow.add_node("intake", intake_node)
workflow.add_node("fetch_customer_context", fetch_customer_context_node)
workflow.add_node("retrieve_policy", retrieve_policy_node)
workflow.add_node("reason_and_decide", reason_and_decide_node)
workflow.add_node("execute_action", execute_action_node)
workflow.add_node("respond", respond_node)

workflow.set_entry_point("intake")
workflow.add_edge("intake", "fetch_customer_context")
workflow.add_edge("fetch_customer_context", "retrieve_policy")
workflow.add_edge("retrieve_policy", "reason_and_decide")

# Route conditionally from reason_and_decide
workflow.add_conditional_edges(
    "reason_and_decide",
    route_after_decide,
    {
        "execute_action": "execute_action",
        "respond": "respond"
    }
)

workflow.add_edge("execute_action", "respond")
workflow.add_edge("respond", END)

agent_app = workflow.compile()
