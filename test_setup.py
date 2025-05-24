#!/usr/bin/env python3
"""
Test script to verify the setup is working correctly
"""
import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_imports():
    """Test that all imports work"""
    print("🧪 Testing imports...")

    try:
        # Test core imports
        from src.agents import SimpleMinecraftAgent  # noqa: F401
        from src.bridge import BridgeConfig, BridgeManager  # noqa: F401
        from src.tools import create_mineflayer_tools  # noqa: F401
        from src.utils import StateManager  # noqa: F401

        print("✅ Core imports successful")

        # Test external dependencies
        import google.adk.agents  # noqa: F401
        import google.adk.tools  # noqa: F401
        import javascript  # noqa: F401
        import redis  # noqa: F401
        import sqlalchemy  # noqa: F401
        import structlog  # noqa: F401

        print("✅ External dependencies imported successfully")

        # Test JavaScript bridge
        from javascript import require  # noqa: F401

        print("✅ JSPyBridge import successful")

        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


async def test_environment():
    """Test environment setup"""
    print("\n🔍 Checking environment...")

    # Check for .env file
    if os.path.exists(".env"):
        print("✅ .env file exists")
    else:
        print("⚠️  .env file not found - using defaults")

    # Check Node modules
    if os.path.exists("node_modules"):
        print("✅ node_modules directory exists")
    else:
        print("❌ node_modules not found - run 'npm install'")
        return False

    # Check for required Node packages
    required_packages = ["mineflayer", "mineflayer-pathfinder", "pythonia", "ws"]
    package_json_path = Path("node_modules")

    missing = []
    for pkg in required_packages:
        if not (package_json_path / pkg).exists():
            missing.append(pkg)

    if missing:
        print(f"❌ Missing Node packages: {', '.join(missing)}")
        return False
    else:
        print("✅ All required Node packages installed")

    return True


async def test_minecraft_connection():
    """Test connection to Minecraft server"""
    print("\n🎮 Testing Minecraft connection...")

    try:
        # Check if Minecraft server is reachable
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)

        host = os.getenv("MC_SERVER_HOST", "localhost")
        port = int(os.getenv("MC_SERVER_PORT", 25565))

        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            print(f"✅ Minecraft server is reachable at {host}:{port}")
            return True
        else:
            print(f"❌ Cannot connect to Minecraft server at {host}:{port}")
            print("   Run 'docker-compose up -d minecraft' to start the server")
            return False

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


async def test_redis_connection():
    """Test Redis connection"""
    print("\n💾 Testing Redis connection...")

    try:
        import redis.asyncio as redis

        client = await redis.from_url("redis://localhost:6379")
        await client.ping()
        await client.close()

        print("✅ Redis is running and accessible")
        return True

    except Exception as e:
        print(f"⚠️  Redis not available: {e}")
        print("   The system will work without Redis but won't persist state")
        return True  # Not critical


async def main():
    """Run all tests"""
    print("🚀 Minecraft Multi-Agent System - Setup Test\n")

    # Run tests
    results = {
        "imports": await test_imports(),
        "environment": await test_environment(),
        "minecraft": await test_minecraft_connection(),
        "redis": await test_redis_connection(),
    }

    # Summary
    print("\n📊 Test Summary:")
    print("-" * 40)

    all_passed = True
    critical_passed = True

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test.capitalize():<15} {status}")

        if not passed:
            all_passed = False
            if test in ["imports", "environment", "minecraft"]:
                critical_passed = False

    print("-" * 40)

    if all_passed:
        print("\n✅ All tests passed! The system is ready to use.")
        print("\nRun: python scripts/run_agent.py agent --interactive")
    elif critical_passed:
        print("\n⚠️  Some optional components failed, but the system should work.")
        print("\nRun: python scripts/run_agent.py agent --interactive")
    else:
        print("\n❌ Critical tests failed. Please fix the issues above.")
        print("\nRun: ./setup_env.sh to set up the environment")
        sys.exit(1)


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
