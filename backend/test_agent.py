import sys
import os
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv()

# Add backend directory to path
sys.path.append(os.path.dirname(__file__))

from agent import agent_app

async def run_test_case_async(customer_id: int, message_content: str):
    print("=" * 60)
    print(f"TESTING AGENT LOOP (ASYNC)")
    print(f"Customer ID: {customer_id}")
    print(f"Message:     {message_content}")
    print("=" * 60)
    
    # Custom token streaming callback for local testing
    async def mock_token_callback(token: str):
        # Print tokens live to stdout as they arrive
        print(token, end="", flush=True)

    # Initialize the state with the human message
    initial_state = {
        "messages": [HumanMessage(content=message_content)],
        "customer_id": customer_id,
        "order_id": "",
        "refund_reason": "",
        "policy_chunks": [],
        "customer_context": {},
        "decision": {},
        "action_result": {},
        "trace": []
    }
    
    # Pass custom streaming callback in config
    config = {
        "configurable": {
            "customer_id": customer_id,
            "on_token": mock_token_callback
        }
    }
    
    try:
        print("\n[STREAMING LLM RESPONSE LIVE]:")
        # Run agent using ainvoke
        result = await agent_app.ainvoke(initial_state, config=config)
        print("\n" + "-" * 60)
        
        # Display traces
        print("\n[REASONING TRACE LOGS]")
        for trace in result.get("trace", []):
            print(f"\n>> Node: {trace['node'].upper()}")
            print(f"   Tool Called: {trace['tool_called']}")
            print(f"   Tool Input:  {trace['tool_input']}")
            print(f"   Tool Output: {trace['tool_output']}")
            print(f"   Reasoning:   {trace['reasoning']}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR RUNNING AGENT]: {e}")
        import traceback
        traceback.print_exc()

def main():
    if len(sys.argv) > 2:
        cust_id = int(sys.argv[1])
        msg = sys.argv[2]
        asyncio.run(run_test_case_async(cust_id, msg))
    else:
        print("Usage: python test_agent.py <customer_id> <message>")
        print("Running default test case for Alice Smith (ID 1)...")
        asyncio.run(run_test_case_async(1, "Hi, I purchased Premium Headphones (ORD-001) but the left speaker stopped working. I'd like a refund."))

if __name__ == "__main__":
    main()
