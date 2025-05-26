#!/usr/bin/env python3
"""
Super Simple Test for Docker Minecraft Server
Just connects and asks for inventory - that's it!
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Mock Google ADK
sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.adk'] = MagicMock()

from dotenv import load_dotenv
from src.agents.simple_agent import SimpleMinecraftAgent
from src.config import get_config

load_dotenv()


async def test_minecraft_inventory():
    """Simple test - connect to your Docker server and ask for inventory"""
    print("🎮 Testing Minecraft Docker Server Connection")
    print("=" * 50)
    
    config = get_config()
    print(f"Server: {config.minecraft_host}:{config.minecraft_port}")
    print(f"Bot: {config.bot_username}")
    
    agent = None
    try:
        print("\n1. Creating agent...")
        agent = SimpleMinecraftAgent("TestBot", config)
        
        print("2. Connecting to Minecraft...")
        await agent.initialize()
        
        print("3. Waiting for connection...")
        await asyncio.sleep(5)  # Give it time to connect and spawn
        
        print("4. Testing inventory query...")
        query = "what do you have in your inventory?"
        print(f"Query: '{query}'")
        
        start_time = time.time()
        response = await agent.process_command(query, player="TestPlayer")
        elapsed = time.time() - start_time
        
        print(f"\n5. Response (took {elapsed:.2f}s):")
        print("-" * 30)
        print(response or "No response")
        print("-" * 30)
        
        if response and len(response) > 5:
            print("\n✅ SUCCESS: Got a response from the agent!")
            print("Your Docker Minecraft server setup is working!")
        else:
            print("\n❌ FAILED: No valid response received")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if agent and agent.bridge:
            try:
                await agent.bridge.close()
                print("\n🧹 Cleaned up connection")
            except:
                pass


if __name__ == "__main__":
    print("🚀 Super Simple Minecraft Test")
    print("Make sure:")
    print("1. Your Docker Minecraft server is running")
    print("2. node src/minecraft/bot.js is running")
    print("3. Bot can connect to the server")
    print()
    
    try:
        asyncio.run(test_minecraft_inventory())
    except KeyboardInterrupt:
        print("\n👋 Test cancelled")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)