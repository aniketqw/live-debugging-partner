# Browser speech manual checklist

Use the synthetic staging script only. Automated tests use fake browser events and do not activate a microphone.

- Open the printed loopback URL in Chrome and, where available, in Safari. Record what works in each browser, including microphone access, interim recognition, speech output, and word boundaries. If a feature is missing or permission is denied, switch to the typed input.
- First test without a microphone. In Harness mode, send the selected rollback request. The active release should stay on the initial version. Click **I’ve read the reply**; it should still stay unchanged. Send a separate **yes** and check that the mock release changes.
- Start a new session. Use headphones to avoid echo, enable **Speak replies**, and select **Start mic**. Read the synthetic rollback request. Verify interim recognition is visible and only final recognition sends a turn. Stop recognition and check that typing still works.
- During a read-back, say “No, it is one zero.” In Harness mode, check that the interrupted phrase records only the completed prefix. If the browser reported no boundary, the prefix can be empty. Confirm only after the new read-back has finished.
- To collect an optional sample, arm the next script attempt with a short pseudonym and read the displayed request once. Follow-up confirmation and cancellation should not register as extra samples. Typed entries and the free-speech card are excluded.
- With the microphone off, use **Compare modes**, then **Replay**. Replay should leave the live mock release and ledger unchanged.

Record what actually happens, including failures. The browser or its provider may process microphone audio; this demo stores no audio. It is a small staging demonstration, not a phone line or a recognizer benchmark.
