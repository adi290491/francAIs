---
title: French Tutor
emoji: 🥐
colorFrom: blue
colorTo: red
sdk: gradio
sdk_version: 6.30.0
python_version: "3.10"
app_file: app.py
pinned: false
---

# francAIs

Personal French tutoring assistant. Upload a French `.mp3`, or switch to **Record** and speak
into any microphone your browser offers, then:

- **Transcribe (French)**: a literal French transcript (Whisper forced to French at temperature 0,
  keeping fillers such as « euh » and « hum »), plus a **Fluency** panel with words per minute and
  every pause of 0.25 s or more between words.
- **Translate (English)**: the transcript translated to English.

Both are also available as **MCP tools** for Claude and other MCP hosts (see below).

Models are served by Hugging Face Inference Providers: `openai/whisper-large-v3` on DeepInfra
(called through the HF router for word-level timestamps) and `Helsinki-NLP/opus-mt-fr-en`.
See [docs/STATUS.md](docs/STATUS.md) for what is built and its known limits.

## Use it as MCP tools (Claude and other hosts)

The app also runs an MCP server (`demo.launch(mcp_server=True)`) with two tools:

| Tool | Input | Returns |
|---|---|---|
| `transcribe_french` | `audio`: link to a French `.mp3` or `.wav` | JSON: `french_text` (verbatim, fillers kept) and `fluency` (words/min, pauses) |
| `translate_to_english` | `audio`: link to a French `.mp3` or `.wav` | the English translation |

They run the same code as the buttons, with the same limits (25 MB by default) and the same
friendly error messages. On the Space, Gradio prefixes each tool with the Space name, so hosts see
**`french_tutor_transcribe_french`** and **`french_tutor_translate_to_english`**. Locally the
names have no prefix.

| | MCP server URL |
|---|---|
| Space | `https://adi290491-french-tutor.hf.space/gradio_api/mcp/` |
| Local (`uv run python app.py`) | `http://127.0.0.1:7860/gradio_api/mcp/` |

### Things to know first

- **The Space is private, so every request needs an HF token** in the header
  `Authorization: Bearer hf_…`. Make a separate **Read** token for this at
  <https://huggingface.co/settings/tokens> (e.g. named `claude-mcp`), so you can revoke it on its
  own. Don't reuse the Space's inference token or the GitHub deploy token.
- **Audio goes in as a link, not an attachment.** The server downloads the file from the link you
  give it, so the link must be a *direct*, publicly reachable link to the `.mp3`/`.wav` file. For
  example, a file in a public Hugging Face dataset (`https://huggingface.co/datasets/<you>/<repo>/resolve/main/clip.mp3`)
  or a GitHub raw link. Claude can't send the server a file you attached in the chat or one on
  your computer, and share pages (a Google Drive "view" link) are not the file itself.
  Anyone with that link can play the clip, so only link to audio you're fine making public.
  Some sites refuse automated downloads. Wikimedia, for example, answers 403 to the server's
  default User-Agent, and the tool then reports only a generic error. Hugging Face dataset links
  work (checked on the Space).
- Gradio's `upload-mcp` helper (for local files) doesn't send a token, so it can't upload to a
  private Space.

### claude.ai (web, and the Claude apps)

Claude can only send the token if your account offers **Request headers** on custom connectors.
That is a beta that is "available to a limited set of organizations"
([Claude docs](https://claude.com/docs/connectors/custom/add-unlisted)).

1. Open **Customize → Connectors**, then select **Add → Add custom connector**.
   (On a Team or Enterprise plan, an Owner adds it under **Organization settings → Connectors →
   Add → Custom**, and you then click **Connect** under Customize → Connectors.)
2. Name: `French Tutor`. URL: `https://adi290491-french-tutor.hf.space/gradio_api/mcp/`.
   Leave **Transport** as it is.
3. Authentication: choose **No sign-in**.
4. Under **Request headers** (inside **Advanced** if the dialog has one screen), add:
   - header name: `authorization`
   - value: `Bearer hf_…`, i.e. the word `Bearer`, a space, then your Read token. Claude sends
     the value exactly as typed.
5. Click **Add**. In a chat, enable the connector from the tools menu and ask, for example:
   *"Use the French Tutor transcribe tool on https://…/clip.mp3 and comment on my pauses."*

- **No "Request headers" section?** Your account doesn't have the beta, and claude.ai can't
  reach a private Space. Use Claude Code (below) instead, or make the Space public, which lets
  anyone who finds it spend your HF credits.
- **Changing or rotating the token:** the auth settings can't be edited after you add the
  connector. Remove it and add it again.
- On Team/Enterprise, a header value is shared by everyone in the organization who uses the
  connector.

### Claude Code

```bash
claude mcp add --transport http --scope user french-tutor \
  https://adi290491-french-tutor.hf.space/gradio_api/mcp/ \
  --header "Authorization: Bearer hf_…"
```

The token is stored in plain text in `~/.claude.json`. Check it with `claude mcp list`, or `/mcp`
inside a session. For the local app: `claude mcp add --transport http french-tutor-local
http://127.0.0.1:7860/gradio_api/mcp/` (no header needed).

### Other hosts (Cursor, VS Code, …)

Most hosts take a JSON entry like this (the key may be `servers` instead of `mcpServers`):

```json
{
  "mcpServers": {
    "french-tutor": {
      "url": "https://adi290491-french-tutor.hf.space/gradio_api/mcp/",
      "headers": { "Authorization": "Bearer hf_…" }
    }
  }
}
```

### Check the server from a terminal

```bash
curl -s https://adi290491-french-tutor.hf.space/gradio_api/mcp/ \
  -H "Authorization: Bearer $HF_READ_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

The reply lists `french_tutor_transcribe_french` and `french_tutor_translate_to_english`. A
`404` instead means the token is missing or can't read the Space.

The button endpoints `/transcribe` and `/translate` are still callable with `gradio_client`, but
they are left out of the API page and the MCP tool list (`api_visibility="undocumented"`),
because their three inputs (mode, upload, recording) make a confusing tool.

## Run locally

```bash
uv sync
cp .env.example .env   # then set HF_TOKEN
uv run python app.py   # http://127.0.0.1:7860
```

## Develop

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
```

After changing dependencies, regenerate the file the Space installs from:

```bash
uv export --no-hashes --no-dev --format requirements-txt > requirements.txt
```
