# DeepSeek-R1:1.5b Setup Guide

## 🚀 Quick Setup

### 1. Install DeepSeek-R1 Model
```bash
# Install the DeepSeek-R1:1.5b model
ollama pull deepseek-r1:1.5b

# Verify installation
ollama list
```

### 2. Run Setup Helper (Optional)
```bash
# Use the automated setup helper
python install_deepseek.py
```

### 3. Test Integration
```bash
# Test the DeepSeek-R1 integration
python test_deepseek_integration.py

# Try the reasoning demo
python demo_deepseek_reasoning.py
```

## 🧠 What is DeepSeek-R1?

DeepSeek-R1 is an advanced reasoning model that excels at:
- **Mathematical Problem Solving**: Step-by-step solutions with detailed explanations
- **Logical Reasoning**: Complex puzzles and analytical thinking
- **Scientific Analysis**: Detailed explanations of scientific concepts
- **Code Analysis**: Understanding and explaining programming concepts
- **Comparative Analysis**: Detailed comparisons and contrasts

## 🎯 Intelligent Model Selection

Your system now automatically selects the best model for each query:

### DeepSeek-R1 is used for:
- Questions containing "why", "how", "explain", "analyze", "compare"
- Mathematical problems and equations
- Step-by-step reasoning requests
- Complex analytical tasks
- Multi-part questions

### Gemma3 is used for:
- Simple greetings ("hello", "hi", "thanks")
- Basic definitions ("what is...")
- Short questions
- Quick responses needed

## 📊 Performance Comparison

| Feature | Gemma3:1b | DeepSeek-R1:1.5b |
|---------|-----------|------------------|
| **Speed** | ⚡ Very Fast | 🐌 Slower |
| **Reasoning** | 🧠 Basic | 🧠🧠🧠 Advanced |
| **Detail** | 📝 Concise | 📚 Comprehensive |
| **Memory** | 💾 Low | 💾💾 Higher |
| **Best For** | Quick answers | Complex analysis |

## 🛠️ Configuration

The system is pre-configured with these settings:

```python
# Default model for general use
OLLAMA_MODEL = "gemma3:1b"

# Specialized models
OLLAMA_REASONING_MODEL = "deepseek-r1:1.5b"  # For complex reasoning
OLLAMA_FAST_MODEL = "gemma3:1b"              # For quick responses

# Available models list
OLLAMA_AVAILABLE_MODELS = "gemma3:1b,deepseek-r1:1.5b"

# Enable automatic model selection
OLLAMA_AUTO_MODEL_SELECTION = True
```

## 🧪 Testing Examples

### Simple Query (Uses Gemma3)
```python
# This will automatically use Gemma3 for fast response
response = await engine.generate_response("Hello, how are you?")
```

### Complex Query (Uses DeepSeek-R1)
```python
# This will automatically use DeepSeek-R1 for detailed reasoning
response = await engine.generate_response(
    "Explain step by step how to solve: 2x² + 5x - 3 = 0"
)
```

### Force Specific Model
```python
# Force DeepSeek-R1 for any query
response = await engine.generate_response(
    "Simple question",
    model="deepseek-r1:1.5b"
)

# Force Gemma3 for any query
response = await engine.generate_response(
    "Complex analysis",
    model="gemma3:1b"
)
```

## 🔧 Troubleshooting

### Model Not Found
```bash
# Check installed models
ollama list

# Install missing model
ollama pull deepseek-r1:1.5b
```

### Slow Responses
- DeepSeek-R1 is naturally slower due to its reasoning capabilities
- Use Gemma3 for faster responses when detailed reasoning isn't needed
- The system automatically balances speed vs quality

### Memory Issues
- DeepSeek-R1 uses more memory than Gemma3
- Monitor system resources during heavy usage
- Consider using smaller models if memory is limited

## 📈 Usage Patterns

### Recommended Usage
- **Quick Questions**: Let auto-selection choose Gemma3
- **Complex Analysis**: Let auto-selection choose DeepSeek-R1
- **Mixed Conversations**: Use auto-selection for optimal experience

### Manual Selection
- **Force Fast**: Use `model="gemma3:1b"` for speed-critical applications
- **Force Reasoning**: Use `model="deepseek-r1:1.5b"` for analysis-heavy tasks

## 🎉 Benefits

1. **Optimal Performance**: Right model for the right task
2. **Better User Experience**: Fast simple responses, detailed complex ones
3. **Resource Efficiency**: Don't waste compute on simple tasks
4. **Scalability**: Easy to add more specialized models
5. **Flexibility**: Manual override when needed

## 🚀 Next Steps

1. **Install DeepSeek-R1**: `ollama pull deepseek-r1:1.5b`
2. **Run Tests**: `python test_deepseek_integration.py`
3. **Try Demo**: `python demo_deepseek_reasoning.py`
4. **Experiment**: Ask both simple and complex questions
5. **Monitor**: Check which model gets selected for different queries

---

Your Second Brain Database now has advanced reasoning capabilities with intelligent model selection! 🧠✨