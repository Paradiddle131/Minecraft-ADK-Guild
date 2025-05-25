#!/usr/bin/env python3
"""
Demo script showcasing ADK pattern implementations
"""
import asyncio
import structlog
from src.agents.adk_patterns import ADKPatternDemonstrator
from src.agents.simple_agent import SimpleMinecraftAgent
from src.config import get_config

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

logger = structlog.get_logger(__name__)


async def main():
    """Run ADK pattern demonstrations"""
    print("\n" + "="*60)
    print("Google ADK Pattern Demonstrations")
    print("="*60)
    
    config = get_config()
    
    # Check for API key
    if not config.google_ai_api_key and not config.google_cloud_project:
        print("\n⚠️  WARNING: No Google AI credentials configured!")
        print("Please set MINECRAFT_AGENT_GOOGLE_AI_API_KEY environment variable")
        print("or configure Google Cloud credentials.")
        print("\nThe demo will run with mock responses.\n")
    
    # Initialize simple agent first
    print("\n1. Initializing SimpleMinecraftAgent with ADK...")
    agent = SimpleMinecraftAgent(config=config)
    
    try:
        await agent.initialize()
        print("✅ Agent initialized successfully")
        
        # Test basic command
        print("\n2. Testing basic command processing...")
        response = await agent.process_command("What can you help me with?")
        print(f"Agent response: {response}")
        
        # Check connection
        print("\n3. Testing Minecraft connection...")
        response = await agent.process_command("Check my position")
        print(f"Position check: {response}")
        
        # Demonstrate ADK patterns if we have a bridge
        if agent.bridge:
            print("\n4. Demonstrating ADK patterns...")
            demonstrator = ADKPatternDemonstrator(agent.bridge, config)
            
            # Show individual patterns
            print("\n   a) Basic LlmAgent:")
            basic_agent = demonstrator.create_basic_llm_agent()
            print(f"      - Name: {basic_agent.name}")
            print(f"      - Output key: {basic_agent.output_key}")
            print(f"      - Tools: {len(basic_agent.tools)} available")
            
            print("\n   b) Sequential Agent (Analyze -> Execute):")
            sequential = demonstrator.create_sequential_demo()
            print(f"      - Name: {sequential.name}")
            print(f"      - Steps: {[agent.name for agent in sequential.sub_agents]}")
            
            print("\n   c) Parallel Agent (Concurrent checks):")
            parallel = demonstrator.create_parallel_demo()
            print(f"      - Name: {parallel.name}")
            print(f"      - Concurrent agents: {[agent.name for agent in parallel.sub_agents]}")
            
            print("\n   d) Loop Agent (Retry mechanism):")
            loop = demonstrator.create_loop_demo()
            print(f"      - Name: {loop.name}")
            print(f"      - Max iterations: {loop.max_iterations}")
            print(f"      - Loop condition key: {loop.loop_condition_key}")
            
            # Run full demonstration if connected
            response = await agent.process_command("check inventory")
            if "not connected" not in response.lower():
                print("\n5. Running full pattern demonstrations...")
                await demonstrator.demonstrate_all_patterns()
            else:
                print("\n5. Skipping full demonstrations (no Minecraft server connection)")
        
        print("\n✅ ADK pattern demonstrations complete!")
        
    except Exception as e:
        logger.error(f"Error during demonstration: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
    
    finally:
        await agent.cleanup()
        print("\n👋 Demo complete. Agent cleaned up.")


if __name__ == "__main__":
    asyncio.run(main())