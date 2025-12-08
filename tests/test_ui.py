
import pytest
from bs4 import BeautifulSoup

def test_index_ui_elements(tmp_path):
    # This test verifies that the index.html contains the expected new UI elements
    # We will verify the content of the actual docs/index.html in the project
    
    index_path = "docs/index.html"
    
    with open(index_path, "r") as f:
        content = f.read()
        
    soup = BeautifulSoup(content, 'html.parser')
    
    # 1. Check for Copy Button
    copy_btn = soup.find("button", class_="copy-button")
    assert copy_btn is not None
    assert "Copy Feed URL" in copy_btn.text
    
    # 2. Check for Instructions Section
    instr_section = soup.find("div", class_="instructions-section")
    assert instr_section is not None
    
    # 3. Check for specific CSS classes in style tags
    assert ".instructions-section" in content
    assert ".copy-button:hover" in content
    
    # 4. Check for Script
    assert "function copyFeedUrl()" in content
    assert "navigator.clipboard.writeText" in content
