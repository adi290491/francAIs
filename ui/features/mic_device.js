() => {
  // Workarounds for Gradio 6.30's microphone recorder:
  // 1. It renders a "Select input device" dropdown (select.mic-select) but never reads it:
  //    recording always calls getUserMedia({audio: true}), the browser default mic. Audio
  //    getUserMedia calls here use the device the user picked instead.
  // 2. It records the moment the device opens, before slow mics (phone, Bluetooth) send
  //    audio. Streams are handed over only once audio flows (see "Warm-up").
  // 3. It lists devices only once. The dropdown is refreshed on "devicechange".
  if (window.__frenchTutorMicDeviceFix) return;
  window.__frenchTutorMicDeviceFix = true;

  const media = navigator.mediaDevices;
  if (!media || typeof media.getUserMedia !== "function") return;

  const original = media.getUserMedia.bind(media);

  // --- Warm-up -------------------------------------------------------------------------
  // getUserMedia resolves as soon as a device is opened, and Gradio starts recording right
  // away. A phone mic (Continuity) or Bluetooth earphones switching to their mic can then
  // deliver pure digital silence for seconds, or not at all on the first open, so the first
  // recording loses its start (or everything). Hand the stream over only once real samples
  // arrive; if none come, reopen the device once (the second open is what works).
  const FIRST_WAIT_MS = 3000;
  const RETRY_WAIT_MS = 4000;

  const style = document.createElement("style");
  style.textContent = `
    button.record-button[data-mic-connecting] { opacity: 0.6; cursor: progress; pointer-events: none; }
    button.record-button[data-mic-connecting]::after { content: "\\00a0· connecting mic…"; }
  `;
  document.head.appendChild(style);

  let connecting = 0;
  const setConnecting = (on) => {
    connecting = Math.max(0, connecting + (on ? 1 : -1));
    for (const button of document.querySelectorAll("button.record-button")) {
      if (connecting) button.setAttribute("data-mic-connecting", "");
      else button.removeAttribute("data-mic-connecting");
    }
  };

  const stopTracks = (stream) => stream && stream.getTracks().forEach((track) => track.stop());

  // Resolves true once the stream carries any non-zero sample, false after `timeoutMs`.
  // If audio can't be inspected here (no running AudioContext), it doesn't block.
  const waitForSignal = (stream, timeoutMs) =>
    new Promise((resolve) => {
      let ctx;
      try {
        ctx = new AudioContext();
      } catch {
        resolve(true);
        return;
      }
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      const started = performance.now();
      const finish = (live) => {
        clearInterval(timer);
        source.disconnect();
        ctx.close().catch(() => {});
        resolve(live);
      };
      ctx.resume().catch(() => {});
      const timer = setInterval(() => {
        const waited = performance.now() - started;
        if (ctx.state !== "running") {
          if (waited > 500) finish(true);
          return;
        }
        analyser.getFloatTimeDomainData(samples);
        if (samples.some((x) => x !== 0)) finish(true);
        else if (waited > timeoutMs) finish(false);
      }, 50);
    });

  // Open `request`; if that exact device is gone, fall back to `fallback` (the caller's own
  // constraints, i.e. the browser default).
  const openDevice = async (request, fallback) => {
    try {
      return await original(request);
    } catch (error) {
      if (request === fallback) throw error;
      console.warn("Selected microphone is unavailable; using the default one.", error);
      return original(fallback);
    }
  };

  const openWhenLive = async (request, fallback) => {
    if (!request || !request.audio || request.video) return openDevice(request, fallback);
    setConnecting(true);
    try {
      let stream = await openDevice(request, fallback);
      if (await waitForSignal(stream, FIRST_WAIT_MS)) return stream;
      console.warn("Microphone opened but sent no audio; reconnecting it.");
      stopTracks(stream);
      stream = await openDevice(request, fallback);
      if (!(await waitForSignal(stream, RETRY_WAIT_MS))) {
        console.warn("Microphone is still silent after reconnecting.");
      }
      return stream;
    } finally {
      setConnecting(false);
    }
  };

  // Connect a newly picked device straight away, so it is warm by the time Record is pressed.
  let warming = null;
  const warmUp = (deviceId) => {
    const request = { audio: { deviceId: { exact: deviceId } } };
    const run = (warming || Promise.resolve())
      .then(() => openWhenLive(request, request))
      .then(stopTracks)
      .catch((error) => console.warn("Could not connect the selected microphone.", error));
    warming = run;
    run.finally(() => {
      if (warming === run) warming = null;
    });
  };

  // Only override once the user has actually picked a device, so the browser default is
  // kept for anyone who never touches the dropdown.
  document.addEventListener(
    "change",
    (event) => {
      const el = event.target;
      if (el instanceof HTMLSelectElement && el.classList.contains("mic-select")) {
        el.dataset.userChosen = "true";
        if (el.value) warmUp(el.value);
      }
    },
    true,
  );

  const chosenDeviceId = () => {
    const picked = [...document.querySelectorAll("select.mic-select[data-user-chosen]")].filter(
      (el) => el.value,
    );
    const visible = picked.find((el) => el.offsetParent !== null);
    return (visible || picked[0] || {}).value || null;
  };

  media.getUserMedia = async (constraints) => {
    if (warming) await warming; // never open the device twice at once
    const deviceId = chosenDeviceId();
    const audio = constraints && constraints.audio;
    const callerChoseDevice = audio && typeof audio === "object" && audio.deviceId;
    if (!deviceId || !audio || callerChoseDevice) return openWhenLive(constraints, constraints);

    const base = typeof audio === "object" ? audio : {};
    const request = { ...constraints, audio: { ...base, deviceId: { exact: deviceId } } };
    return openWhenLive(request, constraints);
  };

  // Gradio also lists devices only once, when the recorder appears, so a phone or headset
  // that connects later (or the real list after mic permission is first granted) never
  // shows up. Keep every open dropdown in sync with the devices the browser offers now:
  // add new ones, and disable (rather than remove) ones that went away, since Gradio owns
  // those <option> nodes.
  const syncDeviceLists = async () => {
    const selects = document.querySelectorAll("select.mic-select");
    if (!selects.length || typeof media.enumerateDevices !== "function") return;
    const inputs = (await media.enumerateDevices()).filter(
      (d) => d.kind === "audioinput" && d.deviceId,
    );
    const available = new Set(inputs.map((d) => d.deviceId));

    for (const select of selects) {
      const listed = new Set([...select.options].map((o) => o.value));
      for (const option of select.options) {
        option.disabled = option.value !== "" && !available.has(option.value);
      }
      for (const device of inputs) {
        if (!listed.has(device.deviceId)) {
          select.add(new Option(device.label || "Microphone", device.deviceId));
        }
      }
      const current = select.selectedOptions[0];
      if (!current || current.disabled || current.value === "") {
        // The picked device disappeared (or nothing was listed yet): go back to the default.
        const first = [...select.options].find((o) => o.value !== "" && !o.disabled);
        if (first) select.value = first.value;
        delete select.dataset.userChosen;
      }
      if ([...select.options].some((o) => o.value !== "" && !o.disabled)) select.disabled = false;
    }
  };
  media.addEventListener?.("devicechange", () => {
    syncDeviceLists().catch((error) => console.warn("Could not refresh microphones.", error));
  });
}
