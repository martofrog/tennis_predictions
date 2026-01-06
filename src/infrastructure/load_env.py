"""
Environment variable loader.

Loads environment variables from .env file if it exists.
"""

import os
from pathlib import Path
from typing import Optional


def load_env_file(env_file: Optional[str] = None) -> None:
    """
    Load environment variables from .env file.
    
    Args:
        env_file: Path to .env file (default: .env in project root)
    """
    if env_file is None:
        # Find project root (assuming this file is in src/infrastructure)
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        env_file = project_root / ".env"
    
    env_path = Path(env_file)
    
    if not env_path.exists():
        return
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE format
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Only set if not already in environment
                    if key and key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        # Silently fail - environment variables might already be set
        pass
