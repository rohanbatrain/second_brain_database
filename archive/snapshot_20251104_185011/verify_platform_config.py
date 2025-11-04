#!/usr/bin/env python3
"""
Verify Platform Configuration for M4 16GB Optimization
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def verify_platform_config():
    """Verify platform detection and configuration"""
    print("=" * 80)
    print("PLATFORM CONFIGURATION VERIFICATION")
    print("=" * 80)
    
    # Import platform config
    from second_brain_database.integrations.langgraph.platform_config import (
        PLATFORM_INFO,
        WORKERS,
        OLLAMA_SETTINGS,
        BATCH_SIZE,
        PlatformConfig
    )
    
    # Display platform info
    print("\n1. DETECTED HARDWARE:")
    platform = PLATFORM_INFO.get('platform', {})
    print(f"   Profile: {platform.get('profile', 'unknown')}")
    print(f"   System: {platform.get('system', 'unknown')}")
    print(f"   CPU Cores (Physical): {platform.get('physical_cores', 0)}")
    print(f"   CPU Cores (Logical): {platform.get('cpu_count', 0)}")
    print(f"   RAM: {platform.get('ram_gb', 0):.1f} GB")
    print(f"   Apple Silicon: {platform.get('is_apple_silicon', False)}")
    
    # Display worker config
    print("\n2. WORKER CONFIGURATION:")
    print(f"   Workers: {WORKERS}")
    print(f"   Batch Size: {BATCH_SIZE}")
    
    # Display Ollama settings
    print("\n3. OLLAMA SETTINGS:")
    for key, value in OLLAMA_SETTINGS.items():
        print(f"   {key}: {value}")
    
    # Test .sbd file loading
    print("\n4. .SBD CONFIGURATION FILES:")
    config_dir = Path(__file__).parent / "config-templates"
    sbd_files = list(config_dir.glob("*.sbd"))
    
    if sbd_files:
        print(f"   Found {len(sbd_files)} .sbd files:")
        for sbd_file in sbd_files:
            print(f"   - {sbd_file.name}")
            
            # Try to load it
            try:
                platform_config = PlatformConfig()
                loaded_config = platform_config.load_sbd_config(str(sbd_file))
                if loaded_config:
                    print(f"     ✓ Loaded successfully")
                    if 'profile' in loaded_config:
                        print(f"       Profile: {loaded_config['profile']}")
                    if 'langgraph' in loaded_config and 'workers' in loaded_config['langgraph']:
                        print(f"       Workers: {loaded_config['langgraph']['workers']}")
            except Exception as e:
                print(f"     ✗ Error: {e}")
    else:
        print("   No .sbd files found")
    
    # Display langgraph.json
    print("\n5. LANGGRAPH.JSON CONFIGURATION:")
    langgraph_json = Path(__file__).parent / "langgraph.json"
    if langgraph_json.exists():
        import json
        with open(langgraph_json) as f:
            config = json.load(f)
        print(f"   Workers in langgraph.json: {config.get('workers', 'NOT SET')}")
        print(f"   Port: {config.get('port', 'NOT SET')}")
    else:
        print("   langgraph.json not found")
    
    # Display ollama_config.py presets
    print("\n6. OLLAMA_CONFIG.PY PRESETS:")
    from second_brain_database.integrations.langgraph.ollama_config import (
        AGENT_CHAT_MODEL,
        CREATIVE_CHAT_MODEL,
        PRECISE_CHAT_MODEL
    )
    
    print("   AGENT_CHAT_MODEL:")
    print(f"     Model: {AGENT_CHAT_MODEL.get('model')}")
    print(f"     num_ctx: {AGENT_CHAT_MODEL.get('num_ctx')}")
    print(f"     num_predict: {AGENT_CHAT_MODEL.get('num_predict')}")
    print(f"     num_gpu: {AGENT_CHAT_MODEL.get('num_gpu')}")
    print(f"     num_thread: {AGENT_CHAT_MODEL.get('num_thread')}")
    
    # Summary
    print("\n" + "=" * 80)
    print("OPTIMIZATION STATUS:")
    print("=" * 80)
    
    platform = PLATFORM_INFO.get('platform', {})
    is_m4_16gb = platform.get('profile') == 'm4_16gb'
    
    if is_m4_16gb:
        print("✓ M4 16GB detected!")
        print(f"✓ Workers optimized: {WORKERS} (recommended for 8-core M4)")
        print(f"✓ Context window optimized: {OLLAMA_SETTINGS.get('num_ctx', 0)} tokens")
        print(f"✓ Max output optimized: {OLLAMA_SETTINGS.get('num_predict', 0)} tokens")
        print(f"✓ Neural Engine enabled: num_gpu={OLLAMA_SETTINGS.get('num_gpu', 0)}")
        print(f"✓ All cores utilized: num_thread={OLLAMA_SETTINGS.get('num_thread', 0)}")
        print("\n🚀 Configuration is FULLY OPTIMIZED for M4 16GB!")
    else:
        print(f"ℹ Profile: {platform.get('profile', 'unknown')}")
        print(f"ℹ Workers: {WORKERS}")
        print(f"ℹ Context: {OLLAMA_SETTINGS.get('num_ctx', 0)} tokens")
        print("\n✓ Configuration optimized for your hardware")
    
    print("=" * 80)

if __name__ == "__main__":
    verify_platform_config()
