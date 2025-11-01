# 🤖 AI Agents Real-World Testing Suite

A comprehensive Streamlit application for testing all Second Brain Database AI agents with realistic user scenarios and problem-solving workflows.

## 🎯 Overview

This testing suite provides an interactive web interface to test all 6 specialized AI agents in real-world scenarios that users would actually encounter. It's designed to validate functionality, performance, and user experience across the entire AI orchestration system.

## 🤖 Agents Tested

### 1. 👨‍👩‍👧‍👦 Family Assistant Agent
**Specializes in:** Family management and coordination
- **Scenarios:**
  - Create families and invite members
  - Manage family token balances and requests
  - Coordinate family shopping and shared assets
- **Real-world use cases:** Family coordination, shared purchases, member management

### 2. 👤 Personal Assistant Agent  
**Specializes in:** Individual user tasks and preferences
- **Scenarios:**
  - Profile and avatar management
  - Security settings and authentication
  - Personal asset tracking and recommendations
- **Real-world use cases:** Profile customization, security management, personal organization

### 3. 🏢 Workspace Collaboration Agent
**Specializes in:** Team collaboration and workspace management
- **Scenarios:**
  - Workspace creation and team setup
  - Team wallet and budget management
  - Project coordination and analytics
- **Real-world use cases:** Team management, project coordination, budget planning

### 4. 🛒 Commerce & Shopping Agent
**Specializes in:** Shopping assistance and asset management
- **Scenarios:**
  - Smart shopping and recommendations
  - Budget planning and spending analysis
  - Deal discovery and collection management
- **Real-world use cases:** Digital asset shopping, budget management, deal hunting

### 5. 🔒 Security & Admin Agent
**Specializes in:** Security monitoring and admin operations
- **Scenarios:**
  - Security event monitoring
  - User management and analytics
  - Performance optimization
- **Real-world use cases:** System administration, security monitoring, performance tuning

### 6. 🎤 Voice & Communication Agent
**Specializes in:** Voice interactions and multi-modal communication
- **Scenarios:**
  - Voice command processing
  - Smart notifications and reminders
  - Multi-modal communication coordination
- **Real-world use cases:** Voice control, accessibility, hands-free operation

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Second Brain Database project setup
- Required dependencies installed

### Installation

1. **Install Streamlit dependencies:**
   ```bash
   pip install -r requirements_streamlit.txt
   ```

2. **Launch the testing suite:**
   ```bash
   python run_ai_agents_test.py
   ```
   
   Or directly with Streamlit:
   ```bash
   streamlit run ai_agents_real_world_test.py
   ```

3. **Open your browser:**
   - The app will automatically open at `http://localhost:8501`
   - If not, navigate to the URL manually

## 🎮 Testing Modes

### 1. Individual Scenarios
- **Purpose:** Test specific scenarios for individual agents
- **Use case:** Debugging specific functionality, focused testing
- **Features:**
  - Select any agent and scenario combination
  - Real-time response viewing
  - Detailed event analysis
  - Error tracking and debugging

### 2. Comprehensive Test
- **Purpose:** Run all scenarios across selected agents
- **Use case:** Full system validation, regression testing
- **Features:**
  - Multi-agent testing
  - Performance metrics
  - Success rate analysis
  - Downloadable results

### 3. Performance Benchmark
- **Purpose:** Performance testing with detailed metrics
- **Use case:** Performance optimization, load testing
- **Features:**
  - Multiple iterations
  - Concurrent session testing
  - Resource utilization monitoring
  - Performance trend analysis

## 🔧 Configuration Options

### Agent Selection
- Choose which agents to test
- Mix and match based on your needs
- All agents selected by default

### User Context
- **Regular User:** Standard permissions for most scenarios
- **Admin User:** Elevated permissions for security agent testing
- **Family Member:** Family-specific permissions for family scenarios

### Test Parameters
- Iteration counts for performance testing
- Concurrent session limits
- Custom scenario inputs

## 📊 Results and Analytics

### Real-time Metrics
- **Execution Time:** How long each scenario takes
- **Events Received:** Number of AI events generated
- **Success Rate:** Percentage of successful completions
- **Error Tracking:** Detailed error analysis

### Performance Analysis
- **Events per Second:** System throughput
- **Average Response Time:** User experience metrics
- **Resource Utilization:** System efficiency
- **Trend Analysis:** Performance over time

### Export Options
- **JSON Results:** Complete test data export
- **Performance Reports:** Formatted analysis
- **Error Logs:** Debugging information
- **Historical Data:** Test history tracking

## 🧪 Test Scenarios Explained

### Family Agent Scenarios

#### Create Family & Invite Members
```
Inputs:
- "Create a new family called 'The Johnsons'"
- "Invite john.doe@email.com to my family"
- "Show me my family members"

Expected Outcomes:
- Family creation confirmation with ID
- Email invitation sent successfully
- Member list display with roles
```

#### Family Token Management
```
Inputs:
- "Show me my family token balance"
- "Request 100 SBD tokens from my family"
- "How much can I spend on family items?"

Expected Outcomes:
- Token balance breakdown by family
- Token request submission confirmation
- Spending guidance and recommendations
```

### Commerce Agent Scenarios

#### Smart Shopping Experience
```
Inputs:
- "Show me what's available in the shop"
- "Recommend items based on my style"
- "Help me buy a new avatar"

Expected Outcomes:
- Shop catalog with filtering
- Personalized recommendations
- Purchase workflow assistance
```

#### Budget Planning & Analysis
```
Inputs:
- "Show me my spending analysis"
- "How much can I afford to spend this month?"
- "Create a budget plan for digital assets"

Expected Outcomes:
- Spending breakdown and trends
- Affordability calculations
- Budget recommendations and limits
```

### Security Agent Scenarios (Admin Only)

#### Security Monitoring
```
Inputs:
- "Show me recent security events"
- "Check system health status"
- "Analyze user activity patterns"

Expected Outcomes:
- Security event log with details
- System health dashboard
- Activity pattern analysis
```

## 🔍 Troubleshooting

### Common Issues

#### "Failed to initialize orchestrator"
- **Cause:** Missing dependencies or configuration
- **Solution:** Check `.sbd` or `.env` file exists, verify database connections

#### "Session not found" errors
- **Cause:** Session cleanup or timeout issues
- **Solution:** Restart the test, check session management settings

#### "Permission denied" for security agent
- **Cause:** Testing with non-admin user context
- **Solution:** Select "Admin User" context for security agent tests

#### Import errors
- **Cause:** Missing Python packages
- **Solution:** Run `pip install -r requirements_streamlit.txt`

### Performance Issues

#### Slow response times
- Check database connection latency
- Verify Redis is running and accessible
- Monitor system resource usage

#### Memory usage growing
- Restart the Streamlit app periodically
- Check for session cleanup issues
- Monitor active session counts

## 🛠️ Development and Customization

### Adding New Scenarios
1. Edit `REAL_WORLD_SCENARIOS` in `ai_agents_real_world_test.py`
2. Add new scenario dictionaries with inputs and expected outcomes
3. Test the new scenarios using Individual Scenarios mode

### Custom User Contexts
1. Modify `TEST_USER_CONTEXTS` to add new user types
2. Adjust permissions and memberships as needed
3. Update the UI selector in the sidebar

### Performance Metrics
1. Extend `AIAgentTester.test_agent_scenario()` for custom metrics
2. Add new performance tracking in the orchestrator
3. Update the results display in the Streamlit UI

## 📈 Best Practices

### Testing Strategy
1. **Start Small:** Test individual scenarios before comprehensive tests
2. **Use Appropriate Context:** Match user context to agent requirements
3. **Monitor Performance:** Watch for degradation over time
4. **Document Issues:** Export results for analysis

### Performance Testing
1. **Baseline First:** Establish performance baselines
2. **Incremental Load:** Gradually increase test complexity
3. **Monitor Resources:** Watch CPU, memory, and network usage
4. **Regular Testing:** Run performance tests regularly

### Error Analysis
1. **Check Logs:** Review detailed error messages
2. **Isolate Issues:** Test individual components
3. **Reproduce Problems:** Use consistent test scenarios
4. **Document Fixes:** Track resolution steps

## 🤝 Contributing

### Reporting Issues
1. Use Individual Scenarios mode to isolate problems
2. Export test results for analysis
3. Include system information and configuration
4. Provide steps to reproduce

### Suggesting Improvements
1. Test new scenarios thoroughly
2. Consider real-world user needs
3. Maintain backward compatibility
4. Document changes clearly

## 📚 Additional Resources

- **Second Brain Database Documentation:** Main project docs
- **AI Orchestration Guide:** Agent architecture details
- **MCP Tools Reference:** Available tool documentation
- **Performance Tuning Guide:** Optimization strategies

## 🎉 Success Metrics

A successful test run should show:
- ✅ **95%+ Success Rate** across all scenarios
- ⚡ **<2s Average Response Time** for most scenarios
- 🔄 **>10 Events/Second** throughput
- 🛡️ **Zero Security Violations** in audit logs
- 💾 **Stable Memory Usage** over time

---

**Happy Testing! 🚀**

*This testing suite helps ensure that all AI agents work seamlessly together to provide an excellent user experience in real-world scenarios.*