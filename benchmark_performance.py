"""
Performance benchmarking script for ADK integration
"""
import asyncio
import time
from statistics import mean, stdev

import structlog
from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import RunConfig
from google.genai import types

from src.config import config

logger = structlog.get_logger(__name__)


async def benchmark_simple_tool_call():
    """Benchmark a simple tool call"""
    
    # Create a simple agent with a tool
    async def test_tool(x: int) -> dict:
        """Simple test tool that returns the square of x"""
        await asyncio.sleep(0.01)  # Simulate some work
        return {"result": x * x}
    
    agent = LlmAgent(
        name="benchmark_agent",
        model=config.adk_model,
        instruction="You are a test agent. When asked to compute something, use the test_tool.",
        tools=[test_tool],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,  # Low temperature for consistent results
            max_output_tokens=100
        )
    )
    
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="benchmark",
        user_id="test"
    )
    
    runner = Runner(
        app_name="benchmark",
        agent=agent,
        session_service=session_service
    )
    
    # Run multiple iterations
    latencies = []
    
    for i in range(5):
        start_time = time.time()
        
        content = types.Content(
            parts=[types.Part(text=f"Compute the square of {i+1}")],
            role="user"
        )
        
        response_text = ""
        async for event in runner.run_async(
            session_id=session.id,
            user_id="test",
            new_message=content,
            run_config=RunConfig(max_llm_calls=5)
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000  # Convert to milliseconds
        latencies.append(latency)
        
        logger.info(f"Iteration {i+1}: {latency:.0f}ms - Response: {response_text[:50]}...")
    
    return latencies


async def benchmark_multi_tool_coordination():
    """Benchmark coordination between multiple tools"""
    
    async def get_data(key: str) -> dict:
        """Get data for a key"""
        await asyncio.sleep(0.02)
        data = {"users": 100, "orders": 500, "revenue": 10000}
        return {"value": data.get(key, 0)}
    
    async def calculate_metric(metric: str, value: int) -> dict:
        """Calculate a business metric"""
        await asyncio.sleep(0.01)
        metrics = {
            "average_order": value / 100 if value > 0 else 0,
            "conversion_rate": 0.15,
            "growth_rate": 0.25
        }
        return {"result": metrics.get(metric, 0)}
    
    agent = LlmAgent(
        name="multi_tool_agent",
        model=config.adk_model,
        instruction="""You are a business analyst agent.
        When asked about metrics:
        1. Use get_data to retrieve the necessary data
        2. Use calculate_metric to compute the metric
        3. Report the result clearly""",
        tools=[get_data, calculate_metric],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=200
        )
    )
    
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="benchmark_multi",
        user_id="test"
    )
    
    runner = Runner(
        app_name="benchmark_multi",
        agent=agent,
        session_service=session_service
    )
    
    latencies = []
    
    queries = [
        "What is the average order value?",
        "Show me the total revenue",
        "Calculate the conversion rate"
    ]
    
    for query in queries:
        start_time = time.time()
        
        content = types.Content(
            parts=[types.Part(text=query)],
            role="user"
        )
        
        tool_calls = 0
        async for event in runner.run_async(
            session_id=session.id,
            user_id="test",
            new_message=content,
            run_config=RunConfig(max_llm_calls=10)
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        tool_calls += 1
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000
        latencies.append(latency)
        
        logger.info(f"Query: '{query}' - {latency:.0f}ms ({tool_calls} tool calls)")
    
    return latencies


async def main():
    """Run all benchmarks"""
    logger.info("Starting ADK Performance Benchmarks")
    
    # Check API key
    if not config.validate_api_key():
        logger.error("No API key found. Please set GOOGLE_API_KEY environment variable.")
        return
    
    try:
        # Benchmark 1: Simple tool calls
        logger.info("\n=== Benchmark 1: Simple Tool Calls ===")
        simple_latencies = await benchmark_simple_tool_call()
        
        if simple_latencies:
            avg_latency = mean(simple_latencies)
            std_latency = stdev(simple_latencies) if len(simple_latencies) > 1 else 0
            
            logger.info(f"Simple tool call performance:")
            logger.info(f"  Average latency: {avg_latency:.0f}ms")
            logger.info(f"  Std deviation: {std_latency:.0f}ms")
            logger.info(f"  Min: {min(simple_latencies):.0f}ms")
            logger.info(f"  Max: {max(simple_latencies):.0f}ms")
        
        # Benchmark 2: Multi-tool coordination
        logger.info("\n=== Benchmark 2: Multi-Tool Coordination ===")
        multi_latencies = await benchmark_multi_tool_coordination()
        
        if multi_latencies:
            avg_latency = mean(multi_latencies)
            std_latency = stdev(multi_latencies) if len(multi_latencies) > 1 else 0
            
            logger.info(f"Multi-tool coordination performance:")
            logger.info(f"  Average latency: {avg_latency:.0f}ms")
            logger.info(f"  Std deviation: {std_latency:.0f}ms")
            logger.info(f"  Min: {min(multi_latencies):.0f}ms")
            logger.info(f"  Max: {max(multi_latencies):.0f}ms")
        
        # Overall summary
        logger.info("\n=== Performance Summary ===")
        all_latencies = simple_latencies + multi_latencies
        p95_latency = sorted(all_latencies)[int(len(all_latencies) * 0.95)]
        
        logger.info(f"Overall P95 latency: {p95_latency:.0f}ms")
        logger.info(f"Meeting Phase 1 target: {'✅ Yes' if p95_latency < 500 else '❌ No'} (target: <500ms)")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}", exc_info=True)


if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    asyncio.run(main())