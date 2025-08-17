from mcpomni_connect.omni_agent import OmniAgent
from mcpomni_connect.memory_store.memory_router import MemoryRouter
from mcpomni_connect.events.event_router import EventRouter
from mcpomni_connect.agents.tools.local_tools_registry import ToolRegistry
# from agentipy.agent import SolanaAgentKit
from dotenv import load_dotenv
import asyncio
import logging
import time
from fastapi import FastAPI, Request,APIRouter
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse
from agentipy.agent import SolanaAgentKit
from agentipy.tools.get_balance import BalanceFetcher
from agentipy.tools.transfer import TokenTransferManager
import os    # Configure logging
from typing import Optional
load_dotenv()


agent = SolanaAgentKit(
        private_key=os.getenv("SOLANA_PRIVATE_KEY"),
        rpc_url="https://api.mainnet-beta.solana.com"  # Mainnet RPC endpoint
    )
async def create_comprehensive_tool_registry() -> ToolRegistry:
    """Create a comprehensive tool registry with various tool types."""
    tool_registry = ToolRegistry()

    @tool_registry.register_tool("get_balance_solana")
    async def get_balance(address:Optional[str]=None) -> str:
        """Get the balance of a Solana address. if no address is provided, it will return the balance of the private key address"""

        try:
            balance_sol = await BalanceFetcher.get_balance(agent,token_address=address)
            return {"status":"success","data":balance_sol}
        except Exception as e:
            return {"status":"error","message":str(e)}

    @tool_registry.register_tool("transfer_solana")
    async def transfer_solana(address:str,amount:float) -> str:
        """Transfer SOL to a Solana address"""
        try:
            sig= await TokenTransferManager.transfer(agent,to=address,amount=amount)
            return {"status":"success","message":"SOL transferred successfully", "data":f"SOL transferred to {address} successfully", "signature":sig}
        except Exception as e:
            return {"status":"error","message":str(e)}
        
   
    return tool_registry
   

    # File system tools

   

@asynccontextmanager
async def lifespan(app: FastAPI):
    memory_store = MemoryRouter(memory_store_type="in_memory")
    event_router = EventRouter(event_store_type="in_memory")

    tool_registry = await create_comprehensive_tool_registry()

    agent = OmniAgent(
            name="solana_agent",
            system_instruction="""
<role>
You are a Solana agent with the ability to check balances and transfer SOL. You are also a comprehensive AI assistant with access to various tools.
</role>

<capabilities>
- Check Solana address balances using get_balance_solana tool
- Transfer SOL using transfer_solana tool
- Provide system information and assistance
</capabilities>

<important_rules>
<rule>You MUST only use tools that are available in the tool registry</rule>
<rule>You MUST NOT provide information or respond to questions outside your tool capabilities</rule>
<rule>CRITICAL: Before ANY SOL transfer, you MUST first check the current balance using get_balance_solana tool</rule>
<rule>You MUST verify that the available balance is sufficient for the requested transfer amount</rule>
<rule>If balance is insufficient, inform the user and do NOT proceed with the transfer</rule>
<rule>Only call transfer_solana after confirming sufficient balance</rule>
<rule>Always provide clear, helpful responses using appropriate tools</rule>
</important_rules>

<transfer_workflow>
When asked to transfer SOL:
1. First call get_balance_solana to check current balance
2. Compare current balance with requested transfer amount
3. If balance >= transfer amount: proceed with transfer_solana
4. If balance < transfer amount: inform user of insufficient funds and current balance
5. Always show both current balance and transfer amount in your response
</transfer_workflow>

<response_format>
Use clear, structured responses. When reporting balances or transfer results, present the information in an organized manner using XML-like tags for clarity.
</response_format>
            """,
            model_config={
                "provider": "openai",
                "model": "gpt-4.1",
                "temperature": 0.7,
                "max_context_length": 50000,
            },
           
            local_tools=tool_registry,
            agent_config={
                "max_steps": 15,
                "tool_call_timeout": 60,
                "request_limit": 1000,
                "memory_config": {"mode": "token_budget", "value": 10000},
            },
            memory_store=memory_store,
            event_router=event_router,
            debug=True,

        )
      
    app.state.agent = agent
    try:
       
        yield 
    except Exception as e:
        logger.error(f"❌ Error in lifespan: {e}")
        await agent.cleanup()
        raise

app = FastAPI(lifespan=lifespan)
router=APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

router = APIRouter()


# agent = SolanaAgentKit(
#     private_key=os.getenv("SOLANA_PRIVATE_KEY"),
#     rpc_url="https://api.mainnet-beta.solana.com",
#     allora_api_key=os.getenv("ALLORA_API_KEY")


# )

@router.get("/events/{session_id}")
async def get_events(session_id: str):
    agent = app.state.agent
    async def eventGenerator():
        try:
            async for event in agent.stream_events(session_id):
                yield f"event: {event.type}\ndata: {event.json()}\n\n"
        except Exception as e:
            yield f"error: {str(e)}\n\n"
    return StreamingResponse(eventGenerator(), media_type="text/event-stream")


@router.post("/chat")
async def chat(message: str, session_id: str = None):
    agent = app.state.agent
    response = await agent.run(message, session_id)
    return response

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)