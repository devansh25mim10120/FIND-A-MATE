# FIND A MATE — Terminal Edition

This folder contains a standalone terminal/CLI adaptation of the uploaded FIND A MATE web project.

## Original project flow

User Interface → Create/Join Session → Session Management → Chat / Media / Moderation → Collaborative Study → Optional AI Support

## Terminal implementation

The CLI keeps the main application logic:

- Create a study session
- Set session duration
- Set message cooldown
- Optional city
- Browse active sessions
- Request to join
- Host approval/rejection
- Member list
- Text chat
- Mute/unmute members
- Kick members
- Session statistics
- End session
- Optional OpenAI study assistance
- Automatic session expiry
- Local persistent storage using SQLite

## Run

Python 3.9+ is recommended.

```bash
cd terminal_app
python main.py
```

No packages are required for the core application.

## Optional AI support

AI support is disabled unless an OpenAI API key is configured.

Install the optional package:

```bash
pip install openai
```

Then configure the key in your environment.

Windows PowerShell:
```powershell
$env:OPENAI_API_KEY="your-key"
python main.py
```

Linux/macOS:
```bash
export OPENAI_API_KEY="your-key"
python main.py
```

You can optionally set:
```bash
OPENAI_MODEL=gpt-5.6
```

## Demo with two users

Open two terminals in the `terminal_app` folder.

Terminal 1:
1. Create a session.
2. Note the Session ID.
3. Stay in the session as host.

Terminal 2:
1. Choose "Request to Join".
2. Enter the Session ID and a nickname.
3. The host approves the request.

The member can then send messages and the host can moderate members.

## Files

- `main.py` — complete terminal application
- `find_a_mate.db` — created automatically after first run
- `README.md` — setup and demo instructions

The `extracted_source` directory contains the usable source files extracted from the uploaded ZIP while excluding Git metadata, dependency caches, and generated JS map files.
