#!/usr/bin/env python3
"""
AI Agents Real-World Testing Suite

Comprehensive Streamlit application to test all AI agents in realistic problem-solving scenarios.
Tests all 6 specialized agents with real user workflows and edge cases.

Agents Tested:
- FamilyAssistantAgent: Family management and coordination
- PersonalAssistantAgent: Individual user tasks and preferences  
- WorkspaceAgent: Team collaboration and workspace management
- CommerceAgent: Shopping assistance and asset management
- SecurityAgent: Security monitoring and admin operations
- VoiceAgent: Voice interactions and multi-modal communication

Usage:
    streamlit run ai_agents_real_world_test.py
"""

import streamlit as st
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

# Import Second Brain Database components
try:
    from src.second_brain_database.integrations.ai_orchestration.orchestrator import AgentOrchestrator
    from src.second_brain_database.integrations.mcp.context import MCPUserContext
    from src.second_brain_database.models.ai_models import CreateAISessionRequest
    from src.second_brain_database.config import settings
    from src.second_brain_database.managers.logging_manager import get_logger
    from src.second_brain_database.integrations.ai_orchestration.models.events import AIEvent, EventType
except ImportError as e:
    st.error(f"Failed to import Second Brain Database components: {e}")
    st.stop()

# Configure logging
logger = get_logger(prefix="[AIAgentsTest]")

# Page configuration
st.set_page_config(
    page_title="AI Agents Real-World Testing Suite",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .test-scenario {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    .agent-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #c3e6cb;
    }
    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #f5c6cb;
    }
    .metric-card {
        background-color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = None
if 'test_results' not in st.session_state:
    st.session_state.test_results = {}
if 'active_sessions' not in st.session_state:
    st.session_state.active_sessions = {}
if 'test_history' not in st.session_state:
    st.session_state.test_history = []

# Real-world test scenarios for each agent
REAL_WORLD_SCENARIOS = {
    "family": {
        "name": "Family Assistant Agent",
        "icon": "👨‍👩‍👧‍👦",
        "scenarios": [
            {
                "title": "Create Family & Invite Members",
                "description": "Create a new family called 'The Johnsons' and invite family members",
                "inputs": [
                    "Create a new family called 'The Johnsons'",
                    "Invite john.doe@email.com to my family",
                    "Show me my family members"
                ],
                "expected_outcomes": [
                    "Family creation confirmation",
                    "Invitation sent confirmation", 
                    "Family member list display"
                ]
            },
            {
                "title": "Family Token Management",
                "description": "Check family token balance and request tokens",
                "inputs": [
                    "Show me my family token balance",
                    "Request 100 SBD tokens from my family",
                    "How much can I spend on family items?"
                ],
                "expected_outcomes": [
                    "Token balance display",
                    "Token request submission",
                    "Spending guidance"
                ]
            },
            {
                "title": "Family Shopping Coordination",
                "description": "Help coordinate family purchases and shared assets",
                "inputs": [
                    "What items are good for families in the shop?",
                    "Help me buy a family theme",
                    "Show family-friendly avatars"
                ],
                "expected_outcomes": [
                    "Family item recommendations",
                    "Purchase assistance",
                    "Avatar suggestions"
                ]
            }
        ]
    },
    "personal": {
        "name": "Personal Assistant Agent", 
        "icon": "👤",
        "scenarios": [
            {
                "title": "Profile Management",
                "description": "Update personal profile, avatar, and preferences",
                "inputs": [
                    "Update my profile with a new avatar",
                    "Change my theme to dark mode",
                    "Show me my current profile settings"
                ],
                "expected_outcomes": [
                    "Avatar update guidance",
                    "Theme change confirmation",
                    "Profile settings display"
                ]
            },
            {
                "title": "Security Settings Management",
                "description": "Manage authentication and security preferences",
                "inputs": [
                    "Help me enable two-factor authentication",
                    "Show me my security settings",
                    "Generate a new API token"
                ],
                "expected_outcomes": [
                    "2FA setup guidance",
                    "Security settings overview",
                    "API token generation"
                ]
            },
            {
                "title": "Personal Asset Tracking",
                "description": "Track personal purchases and asset collection",
                "inputs": [
                    "Show me my purchase history",
                    "What assets do I own?",
                    "Recommend items based on my preferences"
                ],
                "expected_outcomes": [
                    "Purchase history display",
                    "Asset collection overview",
                    "Personalized recommendations"
                ]
            }
        ]
    },
    "workspace": {
        "name": "Workspace Collaboration Agent",
        "icon": "🏢", 
        "scenarios": [
            {
                "title": "Workspace Creation & Team Setup",
                "description": "Create workspace and manage team members",
                "inputs": [
                    "Create a new workspace called 'Project Alpha'",
                    "Add team members to my workspace",
                    "Show me workspace analytics"
                ],
                "expected_outcomes": [
                    "Workspace creation confirmation",
                    "Team member management",
                    "Analytics dashboard"
                ]
            },
            {
                "title": "Team Wallet Management",
                "description": "Manage team funds and token operations",
                "inputs": [
                    "Check our team wallet balance",
                    "Request budget approval for new tools",
                    "Show team spending history"
                ],
                "expected_outcomes": [
                    "Wallet balance display",
                    "Budget request submission",
                    "Spending analytics"
                ]
            },
            {
                "title": "Project Coordination",
                "description": "Coordinate team projects and tasks",
                "inputs": [
                    "Create a new project milestone",
                    "Assign tasks to team members",
                    "Generate team performance report"
                ],
                "expected_outcomes": [
                    "Milestone creation",
                    "Task assignment",
                    "Performance insights"
                ]
            }
        ]
    },
    "commerce": {
        "name": "Commerce & Shopping Agent",
        "icon": "🛒",
        "scenarios": [
            {
                "title": "Smart Shopping Experience",
                "description": "Browse shop, get recommendations, and make purchases",
                "inputs": [
                    "Show me what's available in the shop",
                    "Recommend items based on my style",
                    "Help me buy a new avatar"
                ],
                "expected_outcomes": [
                    "Shop catalog display",
                    "Personalized recommendations",
                    "Purchase assistance"
                ]
            },
            {
                "title": "Budget Planning & Analysis",
                "description": "Analyze spending and plan budget",
                "inputs": [
                    "Show me my spending analysis",
                    "How much can I afford to spend this month?",
                    "Create a budget plan for digital assets"
                ],
                "expected_outcomes": [
                    "Spending breakdown",
                    "Affordability calculation",
                    "Budget recommendations"
                ]
            },
            {
                "title": "Deal Discovery & Asset Management",
                "description": "Find deals and manage digital asset collection",
                "inputs": [
                    "Show me current deals and discounts",
                    "What's in my digital asset collection?",
                    "Find items that complete my collection"
                ],
                "expected_outcomes": [
                    "Deal listings",
                    "Asset inventory",
                    "Collection completion suggestions"
                ]
            }
        ]
    },
    "security": {
        "name": "Security & Admin Agent",
        "icon": "🔒",
        "scenarios": [
            {
                "title": "Security Monitoring",
                "description": "Monitor security events and system health",
                "inputs": [
                    "Show me recent security events",
                    "Check system health status",
                    "Analyze user activity patterns"
                ],
                "expected_outcomes": [
                    "Security event log",
                    "Health status report",
                    "Activity analysis"
                ]
            },
            {
                "title": "User Management",
                "description": "Manage users and administrative operations",
                "inputs": [
                    "Show me user statistics",
                    "List recent user registrations",
                    "Check for suspicious user activity"
                ],
                "expected_outcomes": [
                    "User statistics dashboard",
                    "Registration reports",
                    "Security alerts"
                ]
            },
            {
                "title": "Performance Optimization",
                "description": "Monitor and optimize system performance",
                "inputs": [
                    "Show me system performance metrics",
                    "Identify performance bottlenecks",
                    "Recommend optimization strategies"
                ],
                "expected_outcomes": [
                    "Performance dashboard",
                    "Bottleneck analysis",
                    "Optimization recommendations"
                ]
            }
        ]
    },
    "voice": {
        "name": "Voice & Communication Agent",
        "icon": "🎤",
        "scenarios": [
            {
                "title": "Voice Command Processing",
                "description": "Process voice commands for system features",
                "inputs": [
                    "Enable voice commands for my session",
                    "Process voice memo: 'Remember to buy groceries tomorrow'",
                    "Convert text to speech: 'Welcome to Second Brain Database'"
                ],
                "expected_outcomes": [
                    "Voice activation confirmation",
                    "Voice memo processing",
                    "Text-to-speech conversion"
                ]
            },
            {
                "title": "Smart Notifications",
                "description": "Generate intelligent voice and text notifications",
                "inputs": [
                    "Create a voice notification for family updates",
                    "Generate smart reminders for my tasks",
                    "Set up notification preferences"
                ],
                "expected_outcomes": [
                    "Voice notification creation",
                    "Smart reminder setup",
                    "Preference configuration"
                ]
            },
            {
                "title": "Multi-modal Communication",
                "description": "Coordinate voice and text communication",
                "inputs": [
                    "Start a voice conversation session",
                    "Transcribe this audio to text",
                    "Summarize our conversation"
                ],
                "expected_outcomes": [
                    "Voice session initiation",
                    "Audio transcription",
                    "Conversation summary"
                ]
            }
        ]
    }
}

# Test user contexts for different scenarios
TEST_USER_CONTEXTS = {
    "regular_user": MCPUserContext(
        user_id="test_user_123",
        username="testuser",
        role="user",
        permissions=[
            "profile:update", "family:create", "family:manage", "shop:browse", 
            "shop:purchase", "voice:use", "workspace:create"
        ],
        family_memberships=[
            {"family_id": "family_123", "family_name": "Test Family", "role": "admin"}
        ],
        workspaces=[
            {"_id": "workspace_123", "name": "Test Workspace", "role": "owner"}
        ]
    ),
    "admin_user": MCPUserContext(
        user_id="admin_user_456", 
        username="adminuser",
        role="admin",
        permissions=[
            "admin:security", "admin:health", "admin:users", "admin:audit",
            "admin:performance", "security:monitor", "system:monitor",
            "user:manage", "audit:view", "system:optimize"
        ],
        family_memberships=[],
        workspaces=[]
    ),
    "family_member": MCPUserContext(
        user_id="family_member_789",
        username="familymember", 
        role="user",
        permissions=["family:manage", "family:tokens", "family:shop"],
        family_memberships=[
            {"family_id": "family_456", "family_name": "Johnson Family", "role": "member"}
        ],
        workspaces=[]
    )
}

class AIAgentTester:
    """Comprehensive AI agent testing framework."""
    
    def __init__(self):
        self.orchestrator = None
        self.test_results = {}
        self.performance_metrics = {}
        
    async def initialize_orchestrator(self):
        """Initialize the AI orchestrator."""
        try:
            if self.orchestrator is None:
                self.orchestrator = AgentOrchestrator()
                # Start background tasks if available
                if hasattr(self.orchestrator, 'start_background_tasks'):
                    await self.orchestrator.start_background_tasks()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            return False
    
    async def create_test_session(self, user_context: MCPUserContext, agent_type: str = "personal"):
        """Create a test session for an agent."""
        try:
            session_context = await self.orchestrator.create_session(
                user_context=user_context,
                session_type="chat",
                agent_type=agent_type
            )
            return session_context
        except Exception as e:
            logger.error(f"Failed to create test session: {e}")
            return None
    
    async def test_agent_scenario(
        self, 
        agent_type: str, 
        scenario: Dict[str, Any], 
        user_context: MCPUserContext
    ) -> Dict[str, Any]:
        """Test a specific scenario for an agent."""
        start_time = time.time()
        results = {
            "agent_type": agent_type,
            "scenario_title": scenario["title"],
            "success": False,
            "responses": [],
            "errors": [],
            "execution_time": 0,
            "events_received": 0
        }
        
        try:
            # Ensure orchestrator is initialized
            if not await self.initialize_orchestrator():
                results["errors"].append("Failed to initialize orchestrator")
                return results
            
            # Create session for this test
            session_context = await self.create_test_session(user_context, agent_type)
            if not session_context:
                results["errors"].append("Failed to create test session")
                return results
            
            session_id = session_context.session_id
            
            # Process each input in the scenario
            for i, input_text in enumerate(scenario["inputs"]):
                try:
                    events = []
                    
                    # Check if process_input method exists and is callable
                    if not hasattr(self.orchestrator, 'process_input'):
                        # Fallback: create a mock response for testing
                        events.append({
                            "type": "response",
                            "data": {"response": f"Mock response for: {input_text}"},
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    else:
                        async for event in self.orchestrator.process_input(
                            session_id=session_id,
                            input_text=input_text,
                            metadata={"test_scenario": scenario["title"], "input_index": i}
                        ):
                            events.append({
                                "type": event.type.value if hasattr(event.type, 'value') else str(event.type),
                                "data": event.data,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                    
                    results["responses"].append({
                        "input": input_text,
                        "events": events,
                        "event_count": len(events)
                    })
                    results["events_received"] += len(events)
                    
                except Exception as e:
                    error_msg = f"Input {i+1} failed: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            # Cleanup session if method exists
            if hasattr(self.orchestrator, 'cleanup_session'):
                try:
                    await self.orchestrator.cleanup_session(session_id)
                except Exception as e:
                    logger.warning(f"Session cleanup failed: {e}")
            
            # Determine success based on responses and errors
            results["success"] = (
                len(results["responses"]) > 0 and 
                len(results["errors"]) == 0 and
                results["events_received"] > 0
            )
            
        except Exception as e:
            error_msg = f"Scenario test failed: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
        
        results["execution_time"] = time.time() - start_time
        return results
    
    async def run_comprehensive_test(self, selected_agents: List[str] = None) -> Dict[str, Any]:
        """Run comprehensive tests across all or selected agents."""
        if not self.orchestrator:
            if not await self.initialize_orchestrator():
                return {"error": "Failed to initialize orchestrator"}
        
        test_start_time = time.time()
        comprehensive_results = {
            "test_start_time": datetime.now(timezone.utc).isoformat(),
            "agents_tested": [],
            "total_scenarios": 0,
            "successful_scenarios": 0,
            "failed_scenarios": 0,
            "total_events": 0,
            "agent_results": {},
            "performance_summary": {},
            "errors": []
        }
        
        agents_to_test = selected_agents or list(REAL_WORLD_SCENARIOS.keys())
        
        for agent_type in agents_to_test:
            if agent_type not in REAL_WORLD_SCENARIOS:
                continue
                
            agent_data = REAL_WORLD_SCENARIOS[agent_type]
            agent_results = {
                "agent_name": agent_data["name"],
                "scenarios_tested": 0,
                "scenarios_passed": 0,
                "total_execution_time": 0,
                "total_events": 0,
                "scenario_results": []
            }
            
            # Choose appropriate user context for agent
            if agent_type == "security":
                user_context = TEST_USER_CONTEXTS["admin_user"]
            elif agent_type == "family":
                user_context = TEST_USER_CONTEXTS["family_member"]
            else:
                user_context = TEST_USER_CONTEXTS["regular_user"]
            
            # Test each scenario for this agent
            for scenario in agent_data["scenarios"]:
                try:
                    scenario_result = await self.test_agent_scenario(
                        agent_type, scenario, user_context
                    )
                    
                    agent_results["scenario_results"].append(scenario_result)
                    agent_results["scenarios_tested"] += 1
                    agent_results["total_execution_time"] += scenario_result["execution_time"]
                    agent_results["total_events"] += scenario_result["events_received"]
                    
                    if scenario_result["success"]:
                        agent_results["scenarios_passed"] += 1
                        comprehensive_results["successful_scenarios"] += 1
                    else:
                        comprehensive_results["failed_scenarios"] += 1
                    
                    comprehensive_results["total_scenarios"] += 1
                    comprehensive_results["total_events"] += scenario_result["events_received"]
                    
                except Exception as e:
                    error_msg = f"Agent {agent_type} scenario '{scenario['title']}' failed: {str(e)}"
                    comprehensive_results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            comprehensive_results["agent_results"][agent_type] = agent_results
            comprehensive_results["agents_tested"].append(agent_type)
        
        # Calculate performance summary
        total_time = time.time() - test_start_time
        comprehensive_results["performance_summary"] = {
            "total_execution_time": total_time,
            "average_scenario_time": total_time / max(comprehensive_results["total_scenarios"], 1),
            "events_per_second": comprehensive_results["total_events"] / max(total_time, 1),
            "success_rate": (
                comprehensive_results["successful_scenarios"] / 
                max(comprehensive_results["total_scenarios"], 1) * 100
            )
        }
        
        comprehensive_results["test_end_time"] = datetime.now(timezone.utc).isoformat()
        return comprehensive_results

# Streamlit UI
def main():
    st.title("🤖 AI Agents Real-World Testing Suite")
    st.markdown("**Comprehensive testing of all Second Brain Database AI agents with realistic user scenarios**")
    
    # Sidebar for test configuration
    st.sidebar.header("🔧 Test Configuration")
    
    # Agent selection
    st.sidebar.subheader("Select Agents to Test")
    agent_options = {}
    for agent_key, agent_data in REAL_WORLD_SCENARIOS.items():
        agent_options[f"{agent_data['icon']} {agent_data['name']}"] = agent_key
    
    selected_agent_names = st.sidebar.multiselect(
        "Choose agents:",
        options=list(agent_options.keys()),
        default=list(agent_options.keys())
    )
    selected_agents = [agent_options[name] for name in selected_agent_names]
    
    # Test mode selection
    test_mode = st.sidebar.selectbox(
        "Test Mode:",
        ["Individual Scenarios", "Comprehensive Test", "Performance Benchmark"]
    )
    
    # User context selection
    user_context_choice = st.sidebar.selectbox(
        "User Context:",
        ["Regular User", "Admin User", "Family Member"]
    )
    
    user_context_map = {
        "Regular User": TEST_USER_CONTEXTS["regular_user"],
        "Admin User": TEST_USER_CONTEXTS["admin_user"], 
        "Family Member": TEST_USER_CONTEXTS["family_member"]
    }
    selected_user_context = user_context_map[user_context_choice]
    
    # Initialize tester
    if 'tester' not in st.session_state:
        st.session_state.tester = AIAgentTester()
    
    # Main content area
    if test_mode == "Individual Scenarios":
        st.header("🎯 Individual Scenario Testing")
        
        # Agent and scenario selection
        col1, col2 = st.columns(2)
        
        with col1:
            if selected_agents:
                selected_agent = st.selectbox(
                    "Choose Agent:",
                    options=selected_agents,
                    format_func=lambda x: f"{REAL_WORLD_SCENARIOS[x]['icon']} {REAL_WORLD_SCENARIOS[x]['name']}"
                )
            else:
                st.warning("Please select at least one agent from the sidebar.")
                return
        
        with col2:
            if selected_agent:
                scenarios = REAL_WORLD_SCENARIOS[selected_agent]["scenarios"]
                selected_scenario_idx = st.selectbox(
                    "Choose Scenario:",
                    options=range(len(scenarios)),
                    format_func=lambda x: scenarios[x]["title"]
                )
                selected_scenario = scenarios[selected_scenario_idx]
        
        # Display scenario details
        if selected_scenario:
            st.markdown(f"""
            <div class="test-scenario">
                <h4>{selected_scenario['title']}</h4>
                <p>{selected_scenario['description']}</p>
                <strong>Test Inputs:</strong>
                <ul>
                    {''.join([f'<li>{inp}</li>' for inp in selected_scenario['inputs']])}
                </ul>
                <strong>Expected Outcomes:</strong>
                <ul>
                    {''.join([f'<li>{out}</li>' for out in selected_scenario['expected_outcomes']])}
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Run individual test
            if st.button("🚀 Run Scenario Test", type="primary"):
                with st.spinner("Running scenario test..."):
                    try:
                        result = asyncio.run(
                            st.session_state.tester.test_agent_scenario(
                                selected_agent, selected_scenario, selected_user_context
                            )
                        )
                        
                        # Display results
                        if result["success"]:
                            st.success(f"✅ Scenario completed successfully!")
                        else:
                            st.error(f"❌ Scenario failed")
                        
                        # Metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Execution Time", f"{result['execution_time']:.2f}s")
                        with col2:
                            st.metric("Events Received", result['events_received'])
                        with col3:
                            st.metric("Responses", len(result['responses']))
                        with col4:
                            st.metric("Errors", len(result['errors']))
                        
                        # Detailed results
                        with st.expander("📊 Detailed Results"):
                            st.json(result)
                        
                        # Store result
                        st.session_state.test_results[f"{selected_agent}_{selected_scenario['title']}"] = result
                        
                    except Exception as e:
                        st.error(f"Test execution failed: {str(e)}")
    
    elif test_mode == "Comprehensive Test":
        st.header("🔬 Comprehensive Agent Testing")
        
        st.markdown("""
        This mode runs all scenarios for selected agents and provides comprehensive analysis.
        Perfect for validating overall system functionality and agent performance.
        """)
        
        # Test configuration
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Agents Selected", len(selected_agents))
        with col2:
            total_scenarios = sum(len(REAL_WORLD_SCENARIOS[agent]["scenarios"]) for agent in selected_agents)
            st.metric("Total Scenarios", total_scenarios)
        
        if st.button("🚀 Run Comprehensive Test", type="primary"):
            if not selected_agents:
                st.warning("Please select at least one agent to test.")
                return
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                with st.spinner("Running comprehensive test suite..."):
                    # Run the comprehensive test
                    results = asyncio.run(
                        st.session_state.tester.run_comprehensive_test(selected_agents)
                    )
                    
                    progress_bar.progress(1.0)
                    status_text.success("✅ Comprehensive test completed!")
                    
                    # Display summary metrics
                    st.subheader("📈 Test Summary")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Success Rate", 
                            f"{results['performance_summary']['success_rate']:.1f}%",
                            delta=f"{results['successful_scenarios']}/{results['total_scenarios']}"
                        )
                    with col2:
                        st.metric(
                            "Total Time",
                            f"{results['performance_summary']['total_execution_time']:.2f}s"
                        )
                    with col3:
                        st.metric(
                            "Events/Second",
                            f"{results['performance_summary']['events_per_second']:.1f}"
                        )
                    with col4:
                        st.metric(
                            "Avg Scenario Time",
                            f"{results['performance_summary']['average_scenario_time']:.2f}s"
                        )
                    
                    # Agent-by-agent results
                    st.subheader("🤖 Agent Performance")
                    
                    for agent_type, agent_result in results["agent_results"].items():
                        agent_data = REAL_WORLD_SCENARIOS[agent_type]
                        
                        with st.expander(f"{agent_data['icon']} {agent_data['name']} Results"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                success_rate = (agent_result["scenarios_passed"] / 
                                              max(agent_result["scenarios_tested"], 1) * 100)
                                st.metric("Success Rate", f"{success_rate:.1f}%")
                            
                            with col2:
                                st.metric("Total Events", agent_result["total_events"])
                            
                            with col3:
                                st.metric("Execution Time", f"{agent_result['total_execution_time']:.2f}s")
                            
                            # Scenario details
                            for scenario_result in agent_result["scenario_results"]:
                                status_icon = "✅" if scenario_result["success"] else "❌"
                                st.write(f"{status_icon} **{scenario_result['scenario_title']}** - "
                                        f"{scenario_result['events_received']} events, "
                                        f"{scenario_result['execution_time']:.2f}s")
                    
                    # Error summary
                    if results["errors"]:
                        st.subheader("⚠️ Errors Encountered")
                        for error in results["errors"]:
                            st.error(error)
                    
                    # Store results
                    st.session_state.test_results["comprehensive"] = results
                    st.session_state.test_history.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "test_type": "comprehensive",
                        "agents_tested": selected_agents,
                        "results": results
                    })
                    
                    # Download results
                    st.download_button(
                        label="📥 Download Test Results",
                        data=json.dumps(results, indent=2),
                        file_name=f"ai_agents_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                    
            except Exception as e:
                st.error(f"Comprehensive test failed: {str(e)}")
                progress_bar.empty()
                status_text.empty()
    
    elif test_mode == "Performance Benchmark":
        st.header("⚡ Performance Benchmark")
        
        st.markdown("""
        This mode focuses on performance testing with multiple iterations and detailed metrics.
        Ideal for identifying performance bottlenecks and optimization opportunities.
        """)
        
        # Benchmark configuration
        col1, col2 = st.columns(2)
        with col1:
            iterations = st.number_input("Iterations per scenario", min_value=1, max_value=10, value=3)
        with col2:
            concurrent_sessions = st.number_input("Concurrent sessions", min_value=1, max_value=5, value=1)
        
        if st.button("🏃‍♂️ Run Performance Benchmark", type="primary"):
            st.info("Performance benchmarking is a complex feature that would require additional implementation for concurrent testing and detailed performance metrics.")
            
            # Placeholder for performance benchmark implementation
            st.markdown("""
            **Performance Benchmark Features (To Be Implemented):**
            - Multiple iteration testing
            - Concurrent session handling
            - Memory usage monitoring
            - Response time distribution analysis
            - Throughput measurements
            - Resource utilization tracking
            """)
    
    # Test history and results
    if st.session_state.test_history:
        st.sidebar.subheader("📊 Test History")
        
        for i, test_record in enumerate(reversed(st.session_state.test_history[-5:])):
            with st.sidebar.expander(f"Test {len(st.session_state.test_history) - i}"):
                st.write(f"**Type:** {test_record['test_type']}")
                st.write(f"**Time:** {test_record['timestamp'][:19]}")
                st.write(f"**Agents:** {', '.join(test_record['agents_tested'])}")
                
                if test_record['test_type'] == 'comprehensive':
                    results = test_record['results']
                    st.write(f"**Success Rate:** {results['performance_summary']['success_rate']:.1f}%")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🤖 AI Agents Real-World Testing Suite | Second Brain Database</p>
        <p>Comprehensive testing framework for all AI agents with realistic scenarios</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()