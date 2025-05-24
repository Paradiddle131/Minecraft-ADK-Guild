"""
Mock implementations for testing without external dependencies
"""


class MockLlmAgent:
    """Mock LLM Agent for testing"""

    def __init__(self, name, model, instruction, description, tools, output_key=None):
        self.name = name
        self.model = model
        self.instruction = instruction
        self.description = description
        self.tools = {tool.name: tool for tool in tools}
        self.output_key = output_key

    async def run(self, session, prompt):
        """Simple command parser for testing"""
        # Simple command parsing for tests
        if "inventory" in prompt.lower():
            return MockResponse("Mock inventory result")
        elif "move to" in prompt.lower():
            return MockResponse("Mock movement result")
        elif "find" in prompt.lower():
            return MockResponse("Mock search result")
        else:
            return MockResponse("Mock response")


class MockResponse:
    """Mock response object"""

    def __init__(self, content):
        self.messages = [MockMessage(content)]


class MockMessage:
    """Mock message object"""

    def __init__(self, content):
        self.content = content


class MockSession:
    """Mock session object"""

    def __init__(self):
        self.id = "mock_session_001"
        self.state = {}


class MockFunctionTool:
    """Mock function tool"""

    def __init__(self, func=None, name=None):
        self.func = func
        self.name = name or (func.__name__ if func else "unknown")


class MockToolContext:
    """Mock tool context"""

    def __init__(self):
        self.state = {}


class MockBridgeManager:
    """Mock bridge manager for testing"""

    def __init__(self, config=None):
        self.config = config
        self.is_connected = False

    async def initialize(self):
        """Mock initialization"""
        self.is_connected = True

    async def execute_command(self, method, **kwargs):
        """Mock command execution"""
        return {"status": "success", "method": method, "args": kwargs}

    async def move_to(self, x, y, z):
        """Mock movement"""
        return {"status": "success", "position": {"x": x, "y": y, "z": z}}

    async def get_position(self):
        """Mock position"""
        return {"x": 0, "y": 64, "z": 0}

    async def get_inventory(self):
        """Mock inventory"""
        return [{"name": "stone", "count": 64, "slot": 0}]

    async def chat(self, message):
        """Mock chat"""
        return {"status": "success", "message": message}

    async def close(self):
        """Mock cleanup"""
        self.is_connected = False


class MockEventStream:
    """Mock event stream for testing"""

    def __init__(self):
        self.handlers = {}

    async def start(self):
        """Mock start"""
        pass

    def register_handler(self, event_type, handler):
        """Mock handler registration"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    async def stop(self):
        """Mock stop"""
        pass


class MockEventProcessor:
    """Mock event processor for testing"""

    def __init__(self):
        self.world_state = {
            "bot_position": {"x": 0, "y": 64, "z": 0},
            "players": [],
            "last_update": "2024-01-01T00:00:00",
        }

    async def process_position_event(self, event):
        """Mock position processing"""
        pass

    async def process_player_event(self, event):
        """Mock player processing"""
        pass

    async def process_block_update(self, event):
        """Mock block update processing"""
        pass

    def get_world_state(self):
        """Get mock world state"""
        return self.world_state
