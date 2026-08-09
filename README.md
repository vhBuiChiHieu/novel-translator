# novel-translator

Local-first CLI tool for translating Chinese web novels into Vietnamese while preserving long-term translation context.

## DeepSeek API

The default provider remains Ollama. To use DeepSeek, set this in the project's `novel.yaml`:

```yaml
model:
  provider: deepseek
  name: deepseek-v4-flash
```

Set the API key only in the environment before translating; do not place it in `novel.yaml` or commit it:

```bash
export NOVEL_TRANSLATOR_DEEPSEEK_API_KEY="your-token"
```

The DeepSeek adapter calls `https://api.deepseek.com/chat/completions` and uses JSON output mode.

See `spec.md` for the V0.1 design and run `novel --help` after installation.
