#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Standalone runner for tranpreprocess_knowledge_word.py
Processes files from input/ → output/ using TextProcessor class
"""

import os
import sys
import io

# Add project dir to path
sys.path.insert(0, os.path.dirname(__file__))

from preprocess_knowledge import TextProcessor


def main():
    """Main runner - process all files in input/ directory"""
    # Ensure UTF-8 output on Windows
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # Initialize processor (paths will be auto-detected relative to this file)
    processor = TextProcessor()
    processor.process_all_files()
    print("\n✓ สำเร็จ!")


if __name__ == "__main__":
    main()
