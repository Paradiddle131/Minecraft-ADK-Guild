#!/usr/bin/env python
"""Demo script to showcase agent communication logging."""
import os

# Enable all logging features
os.environ["MINECRAFT_AGENT_LOG_AGENT_THOUGHTS"] = "true"
os.environ["MINECRAFT_AGENT_LOG_TOOL_CALLS"] = "true"
os.environ["MINECRAFT_AGENT_LOG_VERBOSITY"] = "DEBUG"
os.environ["MINECRAFT_AGENT_USE_EMOJI"] = "true"


from src.agents.terminal_logging import format_agent_output, setup_terminal_logging


def demo_terminal_output():
    """Demonstrate the enhanced terminal output formatting."""
    print("\n" + "=" * 60)
    print("AGENT COMMUNICATION LOGGING DEMO")
    print("=" * 60 + "\n")

    # Setup enhanced terminal logging
    setup_terminal_logging()
    # logger = structlog.get_logger("demo")  # Not used in demo

    # Simulate agent communications
    examples = [
        # Coordinator planning
        (
            "CoordinatorAgent",
            "thought",
            "The user wants to craft sticks. I need to check inventory first, then delegate to CrafterAgent if we have planks, or GathererAgent if we need wood.",
        ),
        # Tool invocation
        ("CoordinatorAgent", "tool_call", "get_inventory()"),
        # Delegation
        ("CoordinatorAgent", "delegation", "Delegating to GathererAgent: gather oak logs for crafting"),
        # Gatherer thinking
        ("GathererAgent", "thought", "I need to find oak logs nearby. Let me search in a 32 block radius."),
        # Gatherer tool use
        ("GathererAgent", "tool_call", "find_blocks(block_type='oak_log', max_distance=32)"),
        # Crafter planning
        ("CrafterAgent", "thought", "I have 4 oak logs. First craft them into planks, then craft sticks."),
        # Crafter actions
        ("CrafterAgent", "tool_call", "craft_item(item_name='oak_planks', quantity=16)"),
        ("CrafterAgent", "tool_call", "craft_item(item_name='stick', quantity=8)"),
        # Results
        ("CrafterAgent", "result", "Successfully crafted 8 sticks"),
        ("CoordinatorAgent", "result", "Task completed! Crafted 8 sticks from oak logs."),
    ]

    print("Simulating agent workflow with enhanced logging:\n")

    for agent, event_type, message in examples:
        # Format and display
        formatted = format_agent_output(agent, message, event_type)
        print(formatted)

        # Small delay for visual effect
        import time

        time.sleep(0.5)

    print("\n" + "=" * 60)
    print("LOGGING FEATURES DEMONSTRATED:")
    print("=" * 60)
    print("✅ Agent thoughts captured with indentation")
    print("✅ Tool calls highlighted with icons")
    print("✅ Agent delegations show clear flow")
    print("✅ Different agents have distinct colors")
    print("✅ Results clearly marked")
    print("\nAll communications are also logged to structured log files!")

    # Show how to check logs
    print("\n📁 Log files location: ./logs/")
    print("   - Console: Pretty-printed with colors")
    print("   - Files: JSON format for analysis")

    # Show environment variable configuration
    print("\n⚙️  Configuration via environment variables:")
    print("   MINECRAFT_AGENT_LOG_AGENT_THOUGHTS=true")
    print("   MINECRAFT_AGENT_LOG_TOOL_CALLS=true")
    print("   MINECRAFT_AGENT_LOG_VERBOSITY=DEBUG")
    print("   MINECRAFT_AGENT_USE_EMOJI=true")


if __name__ == "__main__":
    demo_terminal_output()
