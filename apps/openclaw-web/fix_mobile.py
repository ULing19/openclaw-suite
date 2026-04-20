#!/usr/bin/env python3
import re
from pathlib import Path

INDEX_PATH = Path(__file__).resolve().parent / "static" / "index.html"

with open(INDEX_PATH, 'r') as f:
    content = f.read()

# Fix 1: Change overflow:visible to overflow:visible auto on #loginView, #appView for mobile
# This allows overflow-y to work properly
old = '''  #loginView,
  #appView{
    width:100% !important;
    min-height:100dvh !important;
    height:auto !important;
    max-height:none !important;
    position:relative !important;
    inset:auto !important;
    overflow:visible !important;
    z-index:auto !important;
  }

  #loginView:not(.hidden){
    display:flex !important;
    flex-direction:column !important;
    justify-content:flex-start !important;
    align-items:stretch !important;
    overflow-y:auto !important;
    padding:16px 0 28px 0 !important;
  }'''

new = '''  #loginView,
  #appView{
    width:100% !important;
    min-height:100dvh !important;
    height:auto !important;
    max-height:none !important;
    position:relative !important;
    inset:auto !important;
    overflow:visible auto !important;
    z-index:auto !important;
  }

  #loginView:not(.hidden){
    display:flex !important;
    flex-direction:column !important;
    justify-content:flex-start !important;
    align-items:stretch !important;
    overflow-y:scroll !important;
    -webkit-overflow-scrolling:touch !important;
    padding:16px 0 28px 0 !important;
  }'''

if old in content:
    content = content.replace(old, new)
    print("Mobile CSS fixed!")
else:
    print("Mobile CSS pattern not found")

with open(INDEX_PATH, 'w') as f:
    f.write(content)
print("Done!")
