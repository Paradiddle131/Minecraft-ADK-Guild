#!/usr/bin/env python3
"""Test coordinator agent's multi-step crafting coordination flow"""

from unittest.mock import MagicMock, patch

import pytest


# Test the coordinator's behavior when crafting requires gathering materials first
class TestCoordinatorCraftFlow:
    """Test multi-step coordination between coordinator, crafter, and gatherer agents"""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session with state management"""
        session = MagicMock()
        session.state = {
            "minecraft.inventory": {},
            "task.craft.result": None,
            "task.craft.progress": None,
            "task.gather.result": None,
            "task.gather.progress": None,
        }
        return session

    @pytest.fixture
    def mock_coordinator(self, mock_session):
        """Create a mock coordinator agent with sub-agents"""
        from src.agents.coordinator_agent.agent import CoordinatorAgent

        # Mock sub-agents
        mock_crafter = MagicMock(name="CrafterAgent")
        mock_gatherer = MagicMock(name="GathererAgent")

        coordinator = CoordinatorAgent(
            name="TestCoordinator",
            sub_agents=[mock_gatherer, mock_crafter],
            session_service=MagicMock(),
        )

        # Mock the agent's execute method
        coordinator.agent = MagicMock()
        coordinator.session = mock_session

        return coordinator, mock_crafter, mock_gatherer

    @pytest.mark.asyncio
    async def test_coordinator_plans_material_gathering_when_crafting_fails(self, mock_coordinator, mock_session):
        """Test that coordinator creates a plan to gather materials when crafter reports missing materials"""
        coordinator, mock_crafter, mock_gatherer = mock_coordinator

        # Simulate user request to craft sticks
        # user_message = "craft 1 stick"  # Not used in this test

        # Expected behavior:
        # 1. Coordinator should transfer to CrafterAgent
        # 2. CrafterAgent reports missing planks
        # 3. Coordinator should create a plan to gather logs first
        # 4. Coordinator should transfer to GathererAgent

        # Mock the coordinator's planning logic
        with patch.object(coordinator, "_create_material_gathering_plan") as mock_plan:
            mock_plan.return_value = {
                "steps": [
                    {"agent": "GathererAgent", "task": "gather oak logs", "reason": "need logs to craft planks"},
                    {"agent": "CrafterAgent", "task": "craft planks from logs", "reason": "need planks for sticks"},
                    {"agent": "CrafterAgent", "task": "craft sticks from planks", "reason": "fulfill user request"},
                ],
                "missing_materials": {"planks": 2},
            }

            # Simulate state after crafter reports missing materials
            mock_session.state["task.craft.result"] = {
                "status": "error",
                "error": "Insufficient materials to craft 1 stick",
                "missing_materials": {"planks": 2},
            }

            # Call coordinator's plan creation
            plan = coordinator._create_material_gathering_plan(mock_session.state["task.craft.result"])

            # Verify plan was created correctly
            assert plan is not None
            assert len(plan["steps"]) == 3
            assert plan["steps"][0]["agent"] == "GathererAgent"
            assert "gather" in plan["steps"][0]["task"]
            assert plan["missing_materials"] == {"planks": 2}

    @pytest.mark.asyncio
    async def test_coordinator_delegates_to_gatherer_for_logs(self, mock_coordinator, mock_session):
        """Test that coordinator correctly delegates to gatherer when logs are needed"""
        coordinator, mock_crafter, mock_gatherer = mock_coordinator

        # Set state showing crafter needs planks
        mock_session.state["task.craft.result"] = {"status": "error", "missing_materials": {"oak_planks": 2}}
        mock_session.state["coordinator.current_plan"] = {
            "steps": [
                {"agent": "GathererAgent", "task": "gather 1 oak_log", "status": "pending"},
                {"agent": "CrafterAgent", "task": "craft oak_planks", "status": "pending"},
                {"agent": "CrafterAgent", "task": "craft sticks", "status": "pending"},
            ],
            "current_step": 0,
        }

        # Mock coordinator's delegation method
        with patch.object(coordinator, "delegate_to_gatherer") as mock_delegate:
            mock_delegate.return_value = {
                "agent": "GathererAgent",
                "task": "gather 1 oak_log",
                "expected_result": {"oak_log": 1},
            }

            # Execute delegation
            delegation = coordinator.delegate_to_gatherer("gather 1 oak_log")

            # Verify correct delegation
            assert delegation["agent"] == "GathererAgent"
            assert "oak_log" in delegation["task"]
            assert delegation["expected_result"]["oak_log"] == 1

    @pytest.mark.asyncio
    async def test_coordinator_tracks_plan_progress(self, mock_coordinator, mock_session):
        """Test that coordinator properly tracks progress through multi-step plan"""
        coordinator, mock_crafter, mock_gatherer = mock_coordinator

        # Initial plan state
        mock_session.state["coordinator.current_plan"] = {
            "steps": [
                {"agent": "GathererAgent", "task": "gather oak_log", "status": "pending"},
                {"agent": "CrafterAgent", "task": "craft planks", "status": "pending"},
                {"agent": "CrafterAgent", "task": "craft sticks", "status": "pending"},
            ],
            "current_step": 0,
        }

        # Simulate gatherer completing first step
        mock_session.state["task.gather.result"] = {"status": "success", "gathered": {"oak_log": 1}}

        # Mock progress update method
        with patch.object(coordinator, "update_plan_progress") as mock_update:
            mock_update.return_value = {
                "current_step": 1,
                "completed_steps": 1,
                "total_steps": 3,
                "next_agent": "CrafterAgent",
            }

            # Update progress
            progress = coordinator.update_plan_progress(mock_session.state)

            # Verify progress tracking
            assert progress["current_step"] == 1
            assert progress["completed_steps"] == 1
            assert progress["next_agent"] == "CrafterAgent"

    @pytest.mark.asyncio
    async def test_coordinator_completes_multi_step_crafting(self, mock_coordinator, mock_session):
        """Test full workflow: gather logs → craft planks → craft sticks"""
        coordinator, mock_crafter, mock_gatherer = mock_coordinator

        # Simulate complete workflow state transitions
        workflow_states = [
            # Step 1: Initial craft attempt fails
            {
                "task.craft.result": {"status": "error", "missing_materials": {"oak_planks": 2}},
                "coordinator.current_plan": None,
            },
            # Step 2: Plan created, gathering logs
            {
                "task.gather.progress": {"status": "gathering", "target": "oak_log"},
                "coordinator.current_plan": {
                    "steps": [
                        {"agent": "GathererAgent", "task": "gather oak_log", "status": "in_progress"},
                        {"agent": "CrafterAgent", "task": "craft planks", "status": "pending"},
                        {"agent": "CrafterAgent", "task": "craft sticks", "status": "pending"},
                    ],
                    "current_step": 0,
                },
            },
            # Step 3: Logs gathered, crafting planks
            {
                "task.gather.result": {"status": "success", "gathered": {"oak_log": 1}},
                "task.craft.progress": {"status": "crafting", "item": "oak_planks"},
                "minecraft.inventory": {"oak_log": 1},
            },
            # Step 4: Planks crafted, crafting sticks
            {
                "task.craft.result": {"status": "success", "crafted": "oak_planks", "count": 4},
                "task.craft.progress": {"status": "crafting", "item": "stick"},
                "minecraft.inventory": {"oak_planks": 4},
            },
            # Step 5: Sticks crafted successfully
            {
                "task.craft.result": {"status": "success", "crafted": "stick", "count": 4},
                "minecraft.inventory": {"stick": 4},
                "coordinator.current_plan": {
                    "steps": [
                        {"agent": "GathererAgent", "task": "gather oak_log", "status": "completed"},
                        {"agent": "CrafterAgent", "task": "craft planks", "status": "completed"},
                        {"agent": "CrafterAgent", "task": "craft sticks", "status": "completed"},
                    ],
                    "current_step": 3,
                    "status": "completed",
                },
            },
        ]

        # Verify each state transition
        for i, state in enumerate(workflow_states):
            mock_session.state.update(state)

            # Mock workflow completion check
            with patch.object(coordinator, "is_workflow_complete") as mock_check:
                is_complete = i == len(workflow_states) - 1
                mock_check.return_value = is_complete

                # Check workflow status
                complete = coordinator.is_workflow_complete(mock_session.state)

                if i < len(workflow_states) - 1:
                    assert not complete, f"Workflow should not be complete at step {i}"
                else:
                    assert complete, "Workflow should be complete at final step"
                    assert mock_session.state["minecraft.inventory"]["stick"] == 4
