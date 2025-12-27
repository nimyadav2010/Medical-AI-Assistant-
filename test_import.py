import sys
import os
print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")
try:
    import tools
    print(f"Tools package: {tools}")
    from tools import rag_tool
    print("Import successful")
except Exception as e:
    print(f"Import failed: {e}")
