# HuggingFace Authentication Setup

The Chatterbox-Turbo TTS model requires HuggingFace authentication.

## Quick Setup

1. **Create a HuggingFace account** (if you don't have one):
   - Visit: https://huggingface.co/join

2. **Get your access token**:
   - Go to: https://huggingface.co/settings/tokens
   - Click "New token"
   - Name it (e.g., "audiobook-tts")
   - Select "Read" permissions
   - Copy the token

3. **Login via CLI**:
   ```bash
   huggingface-cli login
   ```
   Paste your token when prompted.

**Alternative**: Set environment variable:
```bash
export HUGGING_FACE_HUB_TOKEN="your_token_here"
```

## Verify Authentication

```bash
huggingface-cli whoami
```

You should see your username if authentication is successful.
