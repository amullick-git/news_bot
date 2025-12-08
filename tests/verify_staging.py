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
    # We patch the underlying libraries used by src/content and src/audio
    with patch("src.content.genai") as mock_genai, \
         patch("src.main.generate_rss_feed") as mock_rss, \
         patch("src.audio.texttospeech") as mock_tts, \
         patch("src.fetcher.feedparser.parse") as mock_feed:
         
        # Setup Gemini Mocks
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Prepare responses for Sequence: 
        # 1. Semantic Filter (JSON list of indices)
        # 2. Script Generation (Text)
        mock_filter_resp = MagicMock()
        mock_filter_resp.text = "[0, 1]"
        
        mock_script_resp = MagicMock()
        mock_script_resp.text = "HOST: MOCKED SCRIPT.\nREPORTER: END."
        
        # side_effect ensures sequential returns
        mock_model.generate_content.side_effect = [mock_filter_resp, mock_script_resp]
        
        # Mock TTS response
        mock_client = MagicMock()
        mock_tts.TextToSpeechClient.return_value = mock_client
        mock_client.synthesize_speech.return_value.audio_content = b"fake_audio"
        
        # Mock Feed Metadata (Critical: must avoid Mocks leaking into source names)
        mock_feed.return_value.feed = {"title": "Test News Source"}
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
        
    try:
        # 1. Mock External APIs ... (existing code, conceptually)
        # We need to wrap the WHOLE thing or just the part after we start messing with files.
        # Actually easiest to wrap from step 4 (Running stage script) or just move cleanup to finally block of the function?
        # Let's wrap the checking logic.

        # ... (steps 1-3 are setup/run, already done by the time we get here in the flow, but wait, the file executes linearly)
        # The structure is specific. Let's rewrite the end of verify_staging function.
        
        # 4. Run the staging script
        print("\nRunning scripts/stage_artifacts.sh...")
        subprocess.check_call(["./scripts/stage_artifacts.sh"])
        
        # 5. Verify that NO unstaged changes remain (for the files we care about)
        print("\nVerifying staging...")
        final_status = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8")
        print(f"Git status after staging:\n{final_status}")
        
        lines = final_status.splitlines()
        unstaged_files = []
        for line in lines:
            code = line[:2]
            path = line[3:]
            
            if path == "feed.xml": continue 
            if path.endswith(".py"): continue # Ignore source code changes
            
            if "M" in code[1]: # Modified and unstaged
                unstaged_files.append(path)
            elif code == "??" and path.startswith("episodes/"): 
                unstaged_files.append(path)
            elif code == " M" and path == "index.html": 
                 unstaged_files.append(path)
                 
        if unstaged_files:
            print("FAILURE: The following artifacts were modified/created but NOT staged by the script:")
            for f in unstaged_files:
                print(f" - {f}")
            sys.exit(1)
        else:
            print("SUCCESS: All generated artifacts were correctly staged.")

    finally:
        # Cleanup: Undo changes to keep the working directory clean
        print("\nCleaning up verification artifacts...")
        try:
            # Restore modified            # Stage files
            # Note: We now have metrics in metrics/ folder
            # Ensure folder is part of restore target? or just files?
            
            # Check for unstaged changes
            # We expect changes in metrics/metrics_prod.md and metrics/metrics_stats.json
            
            # Restore
            subprocess.call(["git", "restore", "--staged", "docs/index.html", "metrics/metrics_prod.md", "metrics/metrics_stats.json"])
            subprocess.call(["git", "restore", "docs/index.html", "metrics/metrics_prod.md", "metrics/metrics_stats.json"])
            
            # Clean up test output directory if it exists (from manual test runs, though verifying staging usually simulates prod)
            if os.path.exists("test_output"):
                 import shutil
                 shutil.rmtree("test_output")
                 
            # Remove untracked episodes created during test
            subprocess.call("rm docs/episodes/episode_*_test_*.mp3", shell=True)
            subprocess.call("rm docs/episodes/episode_*_test_*.md", shell=True)
            subprocess.call("rm docs/episodes/links_*_test_*.html", shell=True)
            # Cleanup metrics/ if it was created during test and shouldn't be there?
            # Actually metrics/ contains prod files, we shouldn't delete the dir, just the staged changes.
            pass
            # Cleanup test feed.xml if it landed in right place (verify_staging mocks don't actually write it unless we mocked side_effect?)
            # Actually, `verify_staging` mocks `generate_rss_feed` entirely, so no file is written.
            # But just in case, or if we unmock it later.
            pass
        except Exception as e:
            print(f"Warning: Cleanup failed: {e}")

if __name__ == "__main__":
    verify_staging()
