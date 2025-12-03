import os
import sys
import subprocess
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add root to path if needed (usually cwd is in path)
sys.path.append(os.getcwd())
from src import main as bot_main

def verify_staging():
    print("=== Verifying Artifact Staging Logic ===")
    
    # 1. Mock External APIs to avoid keys and costs
    # We need to patch where they are imported in the modules
    with patch("src.content.genai") as mock_genai, \
         patch("src.audio.texttospeech") as mock_tts, \
         patch("src.fetcher.feedparser.parse") as mock_feed:
         
        # Setup Mocks
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        # Mock semantic filtering response
        mock_model.generate_content.return_value.text = "[0, 1]" 
        
        # Mock TTS response
        mock_client = MagicMock()
        mock_tts.TextToSpeechClient.return_value = mock_client
        mock_client.synthesize_speech.return_value.audio_content = b"fake_audio"
        
        # Mock Feed
        now_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        mock_feed.return_value.entries = [
            {"title": "Test News 1", "link": "http://test.com/1", "summary": "Summary 1", "published": now_str},
            {"title": "Test News 2", "link": "http://test.com/2", "summary": "Summary 2", "published": now_str}
        ]
        
        # 2. Run the bot (Dry run / Test mode logic but in current dir)
        print("Running bot with mocks...")
        # Patch sys.argv to simulate command line args
        with patch.object(sys, 'argv', ["main.py", "--duration", "1"]):
            try:
                bot_main.main()
            except SystemExit:
                pass
            except Exception as e:
                print(f"Bot failed: {e}")
                sys.exit(1)
                
    # 3. Check for modified files
    print("\nChecking git status...")
    # We expect files to be modified/untracked.
    status_output = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8")
    print(f"Git status before staging:\n{status_output}")
    
    if not status_output.strip():
        print("WARNING: No files were modified by the bot. Verification might be invalid.")
        # This might happen if mocks didn't trigger file writes.
        
    # 4. Run the staging script
    print("\nRunning scripts/stage_artifacts.sh...")
    subprocess.check_call(["./scripts/stage_artifacts.sh"])
    
    # 5. Verify that NO unstaged changes remain (for the files we care about)
    # We ignore feed.xml because the script says it's handled separately.
    # We ignore untracked files that are NOT in episodes/ (like __pycache__)
    
    print("\nVerifying staging...")
    final_status = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8")
    print(f"Git status after staging:\n{final_status}")
    
    lines = final_status.splitlines()
    unstaged_files = []
    for line in lines:
        # Status codes: 
        # M  = staged
        #  M = modified (unstaged)
        # ?? = untracked
        code = line[:2]
        path = line[3:]
        
        if path == "feed.xml":
            continue # Ignored as per script comments
            
        if "M" in code[1]: # Modified and unstaged
            unstaged_files.append(path)
        elif code == "??" and path.startswith("episodes/"): # Untracked episode file not picked up
            unstaged_files.append(path)
        elif code == " M" and path == "index.html": # Modified index not staged
             unstaged_files.append(path)
             
    if unstaged_files:
        print("FAILURE: The following files were modified/created but NOT staged by the script:")
        for f in unstaged_files:
            print(f" - {f}")
        sys.exit(1)
    else:
        print("SUCCESS: All generated artifacts were correctly staged.")

if __name__ == "__main__":
    verify_staging()
