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
import os    # Configure logging

load_dotenv()


agent = SolanaAgentKit(
        private_key=os.getenv("SOLANA_PRIVATE_KEY"),
        rpc_url="https://api.mainnet-beta.solana.com"  # Mainnet RPC endpoint
    )
async def create_comprehensive_tool_registry() -> ToolRegistry:
    """Create a comprehensive tool registry with various tool types."""
    tool_registry = ToolRegistry()

    @tool_registry.register_tool("get_balance_solana")
    async def get_balance(address: str) -> str:
        """Get the balance of a Solana address."""
        balance_sol = await BalanceFetcher.get_balance(agent)
        return f"Balance of {address}: {balance_sol } SOL"

   

    # File system tools

   

@asynccontextmanager
async def lifespan(app: FastAPI):
    memory_store = MemoryRouter(memory_store_type="in_memory")
    event_router = EventRouter(event_store_type="in_memory")

    tool_registry = await create_comprehensive_tool_registry()

    agent = OmniAgent(
            name="solana_agent",
            system_instruction="you are a solana agent that can check the balance of a solana address and you are also a comprehensive AI assistant with access to mathematical, text processing, system information, data analysis, and file system tools. You can perform complex calculations, format text, analyze data, and provide system information. Always use the appropriate tools for the task and provide clear, helpful responses. you are not allowed to use any tools that are not in the tool registry or return any information that is not in the tool registry or respond to a question that is not in the tool registry. you are also not allowed to use any tools that are not in the tool registry or return any information that is not in the tool registry or respond to a question that is not in the tool registry. you are also not allowed to use any tools that are not in the tool registry or return any information that is not in the tool registry or respond to a question that is not in the tool registry. you",
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