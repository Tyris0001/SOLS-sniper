# SOLS-sniper
A biome sniper for the roblox game sol's rng which utilizes methods that are faster than most competitors.

This is the free version, for the paid version which has an average sniping time of ~200ms-300ms reach out to me on discord.
`_tyris`
## What makes this sniper stand out
Instead of using the typical `on_message` function which spawns from the discord gateway's websocket connection,
we utilize `on_message_raw_receive` which is nearest to handling the websocket requests raw and unprocessed. 
The reason for `on_message` being slower is because the callback has to process the websocket request and create the respecitve Objects for;
`User`, `Message`, `Channel` etc.

This sniper __will__ out-perform other snipers if ran with a decent internet connection.

**THIS WAS ONLY TESTED ON MACOS, IT SHOULD BE CROSS PLATFORM BUT MAY NOT WORK, IF YOU ARE A WINDOWS USER AND IT DOES NOT WORK FOR YOU, REACH OUT TO ME ON DISCORD**

## Setup
You need python (preferrrably version 3.9)

Once python is installed run:
```sh
pip install -r requirements.txt
```

Edit the `config.json` file;
`biomes`: This is where all keywords should be added which should trigger the sniper
`channels`: List of discord channel IDs which are monitored by the sniper
`token`: Your discord account token which is a member of the SOLS rng discord server (or others)

## To run the sniper
```sh
python3 main.py
```

