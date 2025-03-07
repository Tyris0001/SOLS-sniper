

"""
      _              _
     | |            (_)
     | |_ _   _ _ __ _ ___
     | __| | | | '__| / __|
     | |_| |_| | |  | \__ \
      \__|\__, |_|  |_|___/
  ______   __/ |   SOL's RNG Sniper
 |______| |___/


"""

import os
import psutil
import logging
from typing import Optional, Tuple
import aiohttp
import discord
import json
import re
import subprocess
import platform
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime, timedelta

# Precompile regex patterns for faster matching
PRIVATE_SERVER_PATTERN = re.compile(r'https://www\.roblox\.com/games/(\d+)/.+\?privateServerLinkCode=([\w-]+)')
SHARE_CODE_PATTERN = re.compile(r'https://www\.roblox\.com/share\?code=([a-f0-9]+)&type=Server')
DEEPLINK_PATTERN = re.compile(r'https://www\.roblox\.com/games/start\?placeId=(\d+)(?:&launchData=([^&]+))?')
CSRF_PATTERN = re.compile(r'data-token=\"(.+)\"')
URL_PATTERN = re.compile('(?P<url>https?://[^\s]+)')

# Thread pool for handling subprocess calls
executor = ThreadPoolExecutor(max_workers=4)
config_lock = Lock()

def print_banner():
    print("""
            ▗▖   ▄  ▄▄▄  ▄▄▄▄  ▗▞▀▚▖     ▄▄▄ ▄▄▄▄  ▄ ▄▄▄▄  ▗▞▀▚▖ ▄▄▄ 
            ▐▌   ▄ █   █ █ █ █ ▐▛▀▀▘    ▀▄▄  █   █ ▄ █   █ ▐▛▀▀▘█    
            ▐▛▀▚▖█ ▀▄▄▄▀ █   █ ▝▚▄▄▖    ▄▄▄▀ █   █ █ █▄▄▄▀ ▝▚▄▄▖█    
            ▐▙▄▞▘█                                 █ █               
                                                     ▀   Discord _tyris | Version 3.1b            
    """)
def read_config():
    with config_lock:
        with open('config.json', 'r') as file:
            return json.load(file)


def save_config(config):
    with config_lock:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config, indent=4))
def launch_game(uri):
    """Launch Roblox using the correct URI format"""
    try:
        #print(f"Launching with URI: {uri}")
        if platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', uri])
        elif platform.system() == 'Windows':  # Windows
            subprocess.Popen(uri, shell=True)
        else:
            print(f"Unsupported operating system: {platform.system()}")

    except Exception as e:
        print(f"Error launching game: {e}")


class OptimizedClient(discord.Client):
    def __init__(self):
        super().__init__(enable_debug_events=True)
        self.biomes_cache = set()
        self.update_biomes_cache()
        self.csrf_token = None
        self.last_csrf_update = None
        self.csrf_update_interval = timedelta(minutes=10)
        self.is_processing = False  # Flag to control message processing, locking the sniper if we're in a target biome

    def update_biomes_cache(self):
        """Update the cached set of biomes"""
        config = read_config()
        self.biomes_cache = set(b.lower() for b in config.get('biomes', []))

    async def update_csrf_token(self):
        """Update the CSRF token by fetching it from Roblox"""
        roblox_cookie = read_config().get('cookie')
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.roblox.com',
            'Referer': 'https://www.roblox.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Cookie': '.ROBLOSECURITY='+roblox_cookie
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.roblox.com/", headers=headers) as response:
                    if response.status == 200:
                        text = await response.text()
                        if match := CSRF_PATTERN.search(text):
                            self.csrf_token = match.group(1)
                            self.last_csrf_update = datetime.now()
                            #print(f"Updated CSRF token: {self.csrf_token}")

                            # Save to config
                            config = read_config()
                            config['csrf_token'] = self.csrf_token
                            config['csrf_last_update'] = self.last_csrf_update.isoformat()
                            save_config(config)
                            return True
        except Exception as e:
            print(f"Error updating CSRF token: {e}")
        return False

    async def get_csrf_token(self):
        """Get the current CSRF token, updating if necessary"""
        current_time = datetime.now()
        if (not self.csrf_token or
                not self.last_csrf_update or
                current_time - self.last_csrf_update > self.csrf_update_interval):
            await self.update_csrf_token()
        return self.csrf_token

    async def resolve_share_code(self, share_code, counter=0):
        """Resolve a share code to a private server URL"""
        url = 'https://apis.roblox.com/sharelinks/v1/resolve-link'

        # Get current config for cookie
        config = read_config()
        cookie = config.get('cookie')
        if not cookie:
            print("No cookie found in config")
            return None

        # Get current CSRF token
        csrf_token = await self.get_csrf_token()
        if not csrf_token:
            print("Failed to get CSRF token")
            return None

        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.roblox.com',
            'Referer': 'https://www.roblox.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'x-csrf-token': csrf_token
        }

        data = {
            "linkId": share_code,
            "linkType": "Server"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return f"https://www.roblox.com/games/15532962292/Sols-RNG?privateServerLinkCode={result.get('privateServerInviteData', {}).get('linkCode')}"
                    elif response.status == 403:  # CSRF token expired or private server inaccessible
                        if counter > 5:
                            counter = 0
                            return None

                        print("CSRF token expired, updating...\n", await response.text())
                        await self.update_csrf_token()
                        return await self.resolve_share_code(share_code, counter+1)  # Retry with new token
                    else:
                        print(f"Failed to resolve share code: {response.status}")
                        return None
        except Exception as e:
            print(f"Error resolving share code: {e}")
            return None

    async def on_ready(self):
        #print('Logged in as', self.user)
        print_banner()
        print('Sniper is ready and monitoring for private server links')
        #print('Biomes being sniped: [Windy, Rainy, Hell, Starfall, Glitch, Dreamspace]')
        # Initial CSRF token update
        await self.update_csrf_token()

        # Start CSRF update loop
        self.loop.create_task(self.csrf_update_loop())

    async def csrf_update_loop(self):
        """Background task to periodically update the CSRF token"""
        while True:
            await asyncio.sleep(self.csrf_update_interval.total_seconds())
            await self.update_csrf_token()

    async def kill_roblox_process(self, process: psutil.Process):
        """Safely terminate the Roblox process"""
        try:
            process.terminate()
            await asyncio.sleep(2)  # Give it some time to terminate gracefully
            if process.is_running():
                process.kill()  # Force kill if still running
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Error killing Roblox process: {e}")
        finally:
            self.is_processing = False  # Reset processing flag when done

    async def show_continue_prompt(self):
        """Show a platform-specific prompt for user confirmation"""
        if platform.system() == 'Windows':
            CREATE_NO_WINDOW = 0x08000000
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.call(
                    ['powershell', '-Command',
                     '$host.ui.RawUI.FlushInputBuffer();$response = $host.UI.PromptForChoice("Biome Found", "Do you want to continue?", @("&Yes", "&No"), 1)'],
                    creationflags=CREATE_NO_WINDOW
                )
            )
            return result == 0
        elif platform.system() == 'Darwin':  # macOS
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.call([
                    'osascript',
                    '-e',
                    'tell app "System Events" to display dialog "BIOME FOUND!! SNIPER HAS BEEN PAUSED, PRESS ANY BUTTON TO CONTINUE SNIPING." buttons {"Yes", "No"} default button "Yes"'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            )
            return result == 0
        else:
            print("Unsupported operating system for prompts")
            return False

    async def is_roblox_running(self) -> Tuple[bool, Optional[psutil.Process]]:
        """
        Asynchronously check if Roblox process is running.
        Returns a tuple of (is_running, process_object)
        """
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if 'RobloxPlayer' in proc.info['name']:
                    return True, proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            await asyncio.sleep(0)  # Yield control to event loop
        return False, None

    async def get_memory_usage(self, process: psutil.Process) -> float:
        """
        Asynchronously get memory usage of the Roblox process in MB.
        """
        try:
            return process.memory_info().rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    async def is_game_loaded(self, process: psutil.Process) -> bool:
        """
        Asynchronously determine if the game has loaded by checking memory usage patterns.
        This is a probing approach - when Roblox loads a game, memory usage typically
        stabilizes above a certain threshold, this is somewhat accurate by could more accurately be done by
        checking the game logs for specific events that indicate the game being loaded (I do that in my current sniper)
        """
        MEMORY_THRESHOLD_MB = 200  # Adjust this based on observation
        STABLE_PERIOD_SECONDS = 5
        SAMPLE_INTERVAL = 0.5

        initial_memory = await self.get_memory_usage(process)
        stable_samples = 0
        required_samples = int(STABLE_PERIOD_SECONDS / SAMPLE_INTERVAL)

        for _ in range(required_samples):
            memory_usage = await self.get_memory_usage(process)

            if memory_usage > MEMORY_THRESHOLD_MB:
                stable_samples += 1
            else:
                stable_samples = 0

            await asyncio.sleep(SAMPLE_INTERVAL)

        return stable_samples >= required_samples

    async def get_current_biome(self):
        # Check platform
        log_dir_path = None
        if platform.system() == 'Darwin':  # macOS
            log_dir_path = os.path.expanduser('~/Library/Logs/Roblox')
        elif platform.system() == 'Windows':  # Windows
            log_dir_path = os.path.expanduser("~/AppData/Local/Roblox/logs/")

        latest_log_file, latest_log_time = None, 0

        for filename in os.listdir(log_dir_path):
            file_path = os.path.join(log_dir_path, filename)
            file_time = os.path.getmtime(file_path)
            if file_time > latest_log_time:
                latest_log_time = file_time
                latest_log_file = file_path

        if not latest_log_file:
            return None

        try:
            with open(latest_log_file, 'r', encoding='utf-8', errors='ignore') as log_file:
                logs = log_file.readlines()
                for line in reversed(logs):
                    if '"largeImage":{"hoverText":"' in line:
                        biome = line.split('"largeImage":{"hoverText":"')[1].split('"')[0].strip()
                        return biome
        except FileNotFoundError:
            return None

    async def process_server_link(self, content):
        """Process server links with pre-compiled regex matching"""
        # Don't process if already handling a link
        if self.is_processing:
            return

        self.is_processing = True  # Set processing flag

        try:
            # Check for private server links
            if match := PRIVATE_SERVER_PATTERN.search(content):
                game_id, private_code = match.groups()
                uri = f"roblox://placeId={game_id}&linkCode={private_code}"
                await asyncio.get_event_loop().run_in_executor(executor, launch_game, uri)

            # Check for share codes
            elif match := SHARE_CODE_PATTERN.search(content):
                share_code = match.group(1)
                private_server_url = await self.resolve_share_code(share_code)

                if not private_server_url:
                    print("Failed to resolve share code")
                    self.is_processing = False
                    return False

                if ps_match := PRIVATE_SERVER_PATTERN.search(private_server_url):
                    game_id, private_code = ps_match.groups()
                    uri = f"roblox://placeId=15532962292&linkCode={private_code}"
                    await asyncio.get_event_loop().run_in_executor(executor, launch_game, uri)

            # Check for deeplink format
            elif match := DEEPLINK_PATTERN.search(content):
                place_id, launch_data = match.groups()
                uri = f"roblox://placeId=15532962292"
                if launch_data:
                    uri += f"&launchData={launch_data}"
                await asyncio.get_event_loop().run_in_executor(executor, launch_game, uri)

            roblox_running, roblox_process = await self.is_roblox_running()
            iterator = 0
            while not roblox_running and iterator < 50:
                iterator += 1
                await asyncio.sleep(.5)
                roblox_running, roblox_process = await self.is_roblox_running()

            if iterator >= 50:
                print("Timeout waiting for Roblox to start")
                self.is_processing = False
                return

            game_loaded = await self.is_game_loaded(roblox_process)  # Added await here
            iterator = 0
            while not game_loaded and iterator < 50:
                iterator += 1
                await asyncio.sleep(2)
                game_loaded = await self.is_game_loaded(roblox_process)  # Added await here

            if iterator >= 50:
                print("Timeout waiting for game to load")
                self.is_processing = False
                return

            # Wait a bit for the biome to update in logs
            current_biome = None
            for i in range(5):
                current_biome = await self.get_current_biome()
                await asyncio.sleep(1)

            if current_biome is None:
                print("Could not detect current biome")
                # await self.kill_roblox_process(roblox_process)
                return

            print("Current biome: " + current_biome if current_biome != None else "Unknown")

            if any(biome in current_biome.lower() for biome in self.biomes_cache):
                # Show prompt and wait for user response
                should_continue = await self.show_continue_prompt()
                if not should_continue:
                    # User chose not to continue, close Roblox
                    # #await self.kill_roblox_process(roblox_process)
                    print('')
                else:
                    self.is_processing = False  # Reset flag if user continues
            else:
                # No matching biome, close Roblox
                print('')
                #await self.kill_roblox_process(roblox_process)

        except Exception as e:
            print(f"Error in process_server_link: {e}")
            self.is_processing = False  # Reset flag on error

            # If we have a Roblox process reference, try to kill it on error
            if 'roblox_process' in locals() and roblox_process:
                print('')
                # await self.kill_roblox_process(roblox_process)

    async def on_socket_raw_receive(self, msg):
        try:
            if not msg or self.is_processing:
                return

            # Parse the raw message
            if isinstance(msg, bytes):
                msg = msg.decode('utf-8')

            # Skip non-JSON messages (like heartbeats)
            if not msg.startswith('{'):
                return

            data = json.loads(msg)

            # We only care about message create events
            if data.get('t') != 'MESSAGE_CREATE':
                return

            # Get the message data
            message_data = data.get('d', {})

            # Check if it's from our target channel
            config = read_config()
            if str(message_data.get('channel_id')) not in config.get('channels'):
                return

            content = message_data.get('content', '')
            content_lower = content.lower()

            # Check for biomes
            if any(biome in content_lower for biome in self.biomes_cache):
                asyncio.create_task(self.process_server_link(content))

        except Exception as e:
            print(f"Error in raw socket handler: {e}")
            self.is_processing = False

    async def on_message(self, message):
        if message.author == self.user and message.content.startswith('!'):
            try:
                if message.content[0] == "!":
                    await message.delete()
            except Exception as e:
                print(f"Error deleting message: {e}")

            command_parts = message.content.lower().split(' ')
            command = command_parts[0][1:]

            if command == 'setcookie':
                if len(command_parts) < 2:
                    await message.channel.send("❌ Error: Please provide the cookie value")
                    return

                cookie = message.content.split(' ', 1)[1]  # Get everything after the command
                config = read_config()
                config['cookie'] = cookie
                save_config(config)
                await message.channel.send("✅ Cookie updated successfully")
                return

            elif command == 'add':
                if len(command_parts) < 2:
                    await message.channel.send("❌ Error: Please provide a biome name")
                    return

                arg = command_parts[1].lower()
                config = read_config()
                if arg not in config['biomes']:
                    config['biomes'].append(arg)
                    save_config(config)
                    self.update_biomes_cache()
                    await message.channel.send(f"✅ Added [{arg}] to biome list")
                else:
                    await message.channel.send(f"❌ Error: Biome [{arg}] already exists in the list")

            elif command == 'list':
                config = read_config()
                if not config['biomes']:
                    await message.channel.send("No biomes in the list")
                else:
                    biome_list = "\n".join(f"• {b}" for b in sorted(config['biomes']))
                    await message.channel.send(f"Current biomes:\n{biome_list}")

            elif command == 'remove':
                if len(command_parts) < 2:
                    await message.channel.send("❌ Error: Please provide a biome name")
                    return

                arg = command_parts[1].lower()
                config = read_config()
                try:
                    config['biomes'].remove(arg)
                    save_config(config)
                    self.update_biomes_cache()
                    await message.channel.send(f"✅ Removed [{arg}] from biome list")
                except ValueError:
                    await message.channel.send(f"❌ Error: Biome [{arg}] not found in the list")

            elif command == 'help':
                help_text = (
                    "**Available Commands:**\n\n"
                    "**Biome Management:**\n"
                    "• `!add <biome>` - Add a biome to the list\n"
                    "• `!remove <biome>` - Remove a biome from the list\n"
                    "• `!list` - Show all biomes\n"
                    "• `!setcookie <cookie>` - Update the Roblox cookie"
                )
                await message.channel.send(help_text)
            return

if __name__ == "__main__":
    client = OptimizedClient()
    client.run(read_config().get('token'), log_handler=None)