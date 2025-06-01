# Manual Tests

This directory contains manual test scripts for features that require a running Minecraft server.

## test_movement_progress.py

Tests the movement progress update system to verify that progress messages are sent via chat during pathfinding operations.

To run:
```bash
python tests/manual/test_movement_progress.py
```

This will:
1. Initialize the bot and connect to the server
2. Move the bot 30 blocks away from spawn
3. Display progress updates in chat every 5 seconds
4. Show completion message when arrived