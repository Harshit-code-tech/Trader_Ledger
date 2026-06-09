import urllib.request
import json
import os
import tempfile
import subprocess
import sys
from pathlib import Path
from core.logger import get_logger
import config

logger = get_logger('core.updater')

GITHUB_REPO = "Harshit-code-tech/Trader_Ledger"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def parse_version(version_str: str) -> tuple[int, ...]:
    """Convert version string like 'v1.2.3' to tuple (1, 2, 3) for easy comparison."""
    # Remove 'v' or 'V' if present
    clean_str = version_str.lower().replace('v', '').strip()
    try:
        return tuple(map(int, clean_str.split('.')))
    except ValueError:
        return (0, 0, 0)

def check_for_updates() -> dict | None:
    """
    Check GitHub for a new release.
    Returns a dict with 'version' and 'download_url' if update available, else None.
    """
    try:
        req = urllib.request.Request(LATEST_RELEASE_URL)
        # Add a basic user agent so GitHub API doesn't block us
        req.add_header('User-Agent', 'TraderLedger-AutoUpdater')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            latest_version = data.get('tag_name', '')
            assets = data.get('assets', [])
            
            current_ver_tuple = parse_version(config.APP_VERSION)
            latest_ver_tuple = parse_version(latest_version)
            
            if latest_ver_tuple > current_ver_tuple:
                # Find the executable asset
                download_url = None
                for asset in assets:
                    if asset['name'].endswith('.exe'):
                        download_url = asset['browser_download_url']
                        break
                
                if download_url:
                    return {
                        'version': latest_version,
                        'download_url': download_url,
                        'release_notes': data.get('body', 'No release notes provided.')
                    }
        return None
    except Exception as e:
        logger.error(f"Failed to check for updates: {e}", exc_info=True)
        return None

def download_and_install_update(download_url: str, update_callback=None) -> bool:
    """
    Downloads the installer and runs it.
    update_callback: Optional function that takes (bytes_downloaded, total_bytes)
    """
    try:
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "TraderLedger_Update.exe")
        
        req = urllib.request.Request(download_url)
        req.add_header('User-Agent', 'TraderLedger-AutoUpdater')
        
        with urllib.request.urlopen(req, timeout=15) as response:
            total_size = int(response.getheader('Content-Length', '0'))
            downloaded = 0
            chunk_size = 8192
            
            with open(installer_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if update_callback and total_size > 0:
                        update_callback(downloaded, total_size)
        
        logger.info(f"Update downloaded to {installer_path}. Executing installer.")
        
        # Run installer silently
        # /SILENT means shows progress bar but no clicks required. 
        # /VERYSILENT means completely invisible.
        # /CLOSEAPPLICATIONS tells it to close TraderLedger if it's still running.
        subprocess.Popen([installer_path, "/SILENT", "/CLOSEAPPLICATIONS"])
        
        return True
    except Exception as e:
        logger.error(f"Failed to download/install update: {e}", exc_info=True)
        return False
