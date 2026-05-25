# debug/run_tests.py
# Encoding set to utf-8 as per guidelines
import sys
import os
from dotenv import load_dotenv
import pytest

# Load .env file with explicit utf-8 encoding
load_dotenv(encoding='utf-8')

if __name__ == '__main__':
    # Ensure current directory is in python path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    # Run pytest on tests folder
    sys.exit(pytest.main(['tests']))
