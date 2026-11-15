# Staging Lab browser demo

Plan A is a simulation with no real audio. Plan B adds optional browser speech to the same mock staging service. You can use every demonstration without a microphone by typing or playing a saved trace. The demo cannot run real deployment commands and does not call Ollama.

From the repository root:

~~~sh
(cd demo/web && npm ci --no-audit --no-fund && npm run build)
python3.12 -m demo.server
~~~

Open the local URL printed by the Python server. For frontend development, run the same Python server and run the following in another terminal:

~~~sh
cd demo/web && npm run dev -- --strictPort
~~~

The Vite proxy uses the default loopback backend. If the Python port is busy, run `python3.12 -m demo.server --port 8766` and open the URL printed by the server. For Vite development against that port, use `DEMO_API_TARGET=http://127.0.0.1:8766 npm run dev -- --strictPort` from `demo/web`. No key or environment file is needed. Exact dependency pins and browser research are in the [engineering notes](../docs/vh/RESEARCH_NOTES.md).

Start with **Compare modes** to see what the caller intended, what was misheard, and what each mode actually changed. In **Live session**, send the rollback request from a card, acknowledge the displayed read-back, and send a separate confirmation. **Replay** shows a saved trace without executing its actions. **Benchmark** reads the [scripted benchmark data](../results/vh/runs.csv); see the [report](../results/vh/RESULTS.md) for its limits and comparison method.

Microphone recognition and speech playback are opt-in. The browser or its provider may process speech. Use synthetic phrases only. An optional recognition sample saves the transcript locally under a short pseudonym, without audio, in the ignored results file. To summarize collected samples, run:

~~~sh
python3.12 scripts/calibrate_asr.py
~~~

No human speech samples were collected during development. The [manual checklist](MANUAL_TEST.md) covers microphone access, browser support, interruptions, and echo. For a screen recording, show the mode comparison, then demonstrate that the typed acknowledgment alone leaves the deployment unchanged. Use the typed fallback if speech is unavailable.
