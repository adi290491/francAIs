() => {
  // Workaround for Gradio 6.30's microphone recorder: it renders a "Select input device"
  // dropdown (select.mic-select) but never reads it. Recording always calls
  // getUserMedia({audio: true}), so the browser default mic is used whatever is selected
  // (e.g. a phone chosen in the list records from the laptop instead).
  // This makes audio getUserMedia calls use the device the user picked in that dropdown.
  if (window.__frenchTutorMicDeviceFix) return;
  window.__frenchTutorMicDeviceFix = true;

  const media = navigator.mediaDevices;
  if (!media || typeof media.getUserMedia !== "function") return;

  // Only override once the user has actually picked a device, so the browser default is
  // kept for anyone who never touches the dropdown.
  document.addEventListener(
    "change",
    (event) => {
      const el = event.target;
      if (el instanceof HTMLSelectElement && el.classList.contains("mic-select")) {
        el.dataset.userChosen = "true";
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

  const original = media.getUserMedia.bind(media);
  media.getUserMedia = async (constraints) => {
    const deviceId = chosenDeviceId();
    const audio = constraints && constraints.audio;
    const callerChoseDevice = audio && typeof audio === "object" && audio.deviceId;
    if (!deviceId || !audio || callerChoseDevice) return original(constraints);

    const base = typeof audio === "object" ? audio : {};
    try {
      return await original({ ...constraints, audio: { ...base, deviceId: { exact: deviceId } } });
    } catch (error) {
      // The device was unplugged or disconnected since it was listed: fall back to the default.
      console.warn("Selected microphone is unavailable; using the default one.", error);
      return original(constraints);
    }
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
